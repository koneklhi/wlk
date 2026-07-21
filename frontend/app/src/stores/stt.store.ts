/**
 * @fileoverview STT 세션/전사 상태 — Zustand store.
 *
 * 핵심 불변식: **WS 연결 1개 = 세션 1개.**
 * 빈 프레임(0바이트)을 보내면 서버는 그 세션을 종료하고 이후 오디오를 전부 버린다
 * (audio_processor.py `is_stopping` — 재무장 경로가 없다). 그래서 '재시작'·'재개'·
 * '자동 재연결'·'desync 재동기'는 전부 **같은 동작**이다: 지금 것을 동결하고 새 소켓을 연다.
 * 그 단일 진입점이 beginSession() 이다.
 *
 * 소켓 생성이 한 곳으로 모이면서 예전의 boolean 누더기
 * (userDisconnected / expectServerClose / 리셋 안 되던 reconnectAttempts)가 sessionId 세대
 * 가드 하나로 대체된다 — 이전 세대 소켓의 콜백은 구조적으로 새 세대 상태를 건드릴 수 없다.
 */
import { create } from 'zustand';
import {
  EMPTY_VOLATILE,
  classify,
  isFinalized,
  isRenderable,
  lineKey,
  reconstructLines,
  sameSegment,
} from '@/utils/deltaProtocol';
import { buildWsUrl } from '@/utils/wsUrl';
import { getHealth } from '@/api/health';
import type {
  DiffMessage,
  Segment,
  SnapshotMessage,
  SourceLanguage,
  SttPhase,
  StopIntent,
  VolatileState,
  WsMode,
} from '@/types/stt';

export type BackendStatus = 'unknown' | 'healthy' | 'unhealthy';

/** config 프레임을 이 시간 안에 못 받으면 연결 실패로 본다. 서버는 accept 직후 보낸다. */
const CONFIG_TIMEOUT_MS = 8_000;
/** EOS 후 ready_to_stop 대기 상한. 참조 구현엔 없지만, 없으면 stopping 에서 영구 정지한다. */
const STOP_FLUSH_TIMEOUT_MS = 10_000;
/** 예상치 못한 끊김 자동 재개 백오프. */
export const RESUME_BACKOFF_MS = [500, 1_000, 2_000, 4_000];
export const MAX_AUTO_RESUME = 3;
/** 이 횟수를 넘게 desync 하면 프로토콜 버그로 보고 자동 재동기를 멈춘다. */
const MAX_DESYNC = 3;

export interface PendingResume {
  reason: 'disconnect' | 'desync';
  attempt: number;
}

interface SttStore {
  // ── 세션/연결 ──
  phase: SttPhase;
  stopIntent: StopIntent;
  ws: WebSocket | null;
  /** 연결마다 +1. 모든 소켓 콜백의 stale 가드. */
  sessionId: number;
  /** 다음 연결에 적용할 언어. */
  language: SourceLanguage;
  /** config 가 에코한 실제 적용 언어. 의도대로 걸렸는지 확인용. */
  appliedLanguage: SourceLanguage | null;
  /** config 가 에코한 실제 적용 프로토콜. 요청은 항상 delta. */
  protocol: WsMode;
  useAudioWorklet: boolean;
  /** ready_to_stop 이후 최종 렌더 모드(buffer 를 본문에 정착). */
  isFinalizing: boolean;

  // ── 전사 상태 ──
  /** 서버-권위 lines[] 미러. 새 연결마다 반드시 비운다. */
  serverLines: Segment[];
  /** 현 세션 확정 이력. key = String(id). */
  finalizedHistory: Map<string, Segment>;
  /** 이전 세션들에서 동결된 확정 줄. */
  committedLines: Segment[];
  volatile: VolatileState;

  // ── 복구/진단 ──
  pendingResume: PendingResume | null;
  lastSeq: number;
  desyncCount: number;
  lastError: string | null;
  backendStatus: BackendStatus;

  // ── 액션 ──
  setLanguage: (lang: SourceLanguage) => void;
  /** 유일한 소켓 생성 지점. resume=true 면 현 전사를 committedLines 로 동결하고 이어간다. */
  beginSession: (opts: { resume: boolean }) => Promise<void>;
  /** 오디오 송신 시작을 알린다(실제 인코더 제어는 useAudioRecorder 담당). */
  markRecording: () => void;
  sendAudioChunk: (chunk: Blob | ArrayBuffer) => void;
  /** EOS 전송. 'pause' 는 flush 를 기다리고, 'stop' 은 즉시 전사를 버린다. */
  endSession: (intent: 'pause' | 'stop') => void;
  /** 전사 기록 전체 삭제 → idle. */
  resetTranscript: () => void;
  failSession: (reason: unknown) => void;
  checkBackend: () => Promise<void>;

  // 내부 (소켓 콜백 전용)
  handleMessage: (raw: string) => void;
  _onClose: (e: CloseEvent) => void;
}

/** config 수신 대기 deferred. 세션당 하나. */
let configDeferred: { resolve: () => void; reject: (e: Error) => void } | null = null;
let configTimer: ReturnType<typeof setTimeout> | null = null;
let flushTimer: ReturnType<typeof setTimeout> | null = null;

const clearTimer = (t: ReturnType<typeof setTimeout> | null) => {
  if (t) clearTimeout(t);
  return null;
};

export const useSttStore = create<SttStore>()((set, get) => ({
  phase: 'idle',
  stopIntent: null,
  ws: null,
  sessionId: 0,
  language: 'auto',
  appliedLanguage: null,
  protocol: 'full',
  useAudioWorklet: false,
  isFinalizing: false,

  serverLines: [],
  finalizedHistory: new Map(),
  committedLines: [],
  volatile: { ...EMPTY_VOLATILE },

  pendingResume: null,
  lastSeq: 0,
  desyncCount: 0,
  lastError: null,
  backendStatus: 'unknown',

  setLanguage: (language) => set({ language }),

  // ── 세션 시작 (유일한 소켓 생성 지점) ──────────────────────────────────────
  beginSession: ({ resume }) => {
    const s = get();

    // 기존 소켓은 무조건 정리한다. "이미 OPEN 이면 return" 은 절대 하지 않는다 —
    // 그게 언어 드롭다운 무반응 + 중지 후 재시작 무전사(1연결=1세션)의 원인이었다.
    if (s.ws) {
      try {
        s.ws.close();
      } catch {
        /* 이미 닫힌 소켓 */
      }
    }

    const sessionId = s.sessionId + 1;

    set({
      phase: 'connecting',
      stopIntent: null,
      ws: null,
      sessionId,
      // resume: 현 세션 확정분을 동결. 새 세션은 id 가 0부터 다시 매겨지므로
      // 같은 Map 에 두면 옛 줄을 덮어쓴다.
      committedLines: resume ? [...s.committedLines, ...s.finalizedHistory.values()] : [],
      finalizedHistory: new Map(),
      // 새 연결 = 서버측 새 DiffTracker(seq 1 부터 snapshot). 안 비우면 이전 세션 줄이
      // 꼬리 교체에 섞여 들어간다.
      serverLines: [],
      volatile: { ...EMPTY_VOLATILE },
      lastSeq: 0,
      isFinalizing: false,
      protocol: 'full',
      appliedLanguage: null,
      pendingResume: null,
      lastError: null,
    });

    const stale = () => get().sessionId !== sessionId;

    const ready = new Promise<void>((resolve, reject) => {
      configDeferred = { resolve, reject };
    });

    configTimer = clearTimer(configTimer);
    configTimer = setTimeout(() => {
      if (stale()) return;
      configDeferred?.reject(new Error('서버가 응답하지 않습니다.'));
      configDeferred = null;
      set({ phase: 'error', lastError: '서버가 응답하지 않습니다.' });
    }, CONFIG_TIMEOUT_MS);

    let ws: WebSocket;
    try {
      ws = new WebSocket(buildWsUrl(s.language));
    } catch (e) {
      configTimer = clearTimer(configTimer);
      configDeferred = null;
      set({ phase: 'error', lastError: 'WebSocket 주소가 올바르지 않습니다.' });
      return Promise.reject(e);
    }

    ws.addEventListener('message', (e) => {
      if (!stale() && typeof e.data === 'string') get().handleMessage(e.data);
    });
    ws.addEventListener('error', () => {
      if (!stale()) set({ lastError: '연결 오류가 발생했습니다.' });
    });
    ws.addEventListener('close', (e) => {
      if (!stale()) get()._onClose(e);
    });

    set({ ws });
    return ready.finally(() => {
      configTimer = clearTimer(configTimer);
    });
  },

  markRecording: () => {
    if (get().phase === 'connecting') set({ phase: 'recording' });
  },

  sendAudioChunk: (chunk) => {
    const { ws, phase } = get();
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    // stopping 이후 보낸 오디오는 서버가 경고와 함께 버린다 — 애초에 보내지 않는다.
    if (phase !== 'recording') return;
    ws.send(chunk);
  },

  // ── 세션 종료 ──────────────────────────────────────────────────────────────
  endSession: (intent) => {
    const { ws } = get();

    // EOS = 빈 **바이너리** 프레임. 텍스트 프레임을 보내면 서버가 세션을 죽인다.
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(new ArrayBuffer(0));
      } catch {
        /* 전송 실패해도 아래 정리는 진행 */
      }
    }

    if (intent === 'stop') {
      // 전사를 버리므로 flush 를 기다릴 이유가 없다. 즉시 정리한다.
      // (참조 구현 fullStop 과 동일 — 늦게 오는 ready_to_stop 은 세대 가드로 무시된다.)
      flushTimer = clearTimer(flushTimer);
      try {
        ws?.close();
      } catch {
        /* noop */
      }
      set({
        phase: 'idle',
        stopIntent: null,
        ws: null,
        sessionId: get().sessionId + 1, // 남은 콜백 전부 무효화
        serverLines: [],
        finalizedHistory: new Map(),
        committedLines: [],
        volatile: { ...EMPTY_VOLATILE },
        isFinalizing: false,
        pendingResume: null,
        lastSeq: 0,
        lastError: null,
      });
      return;
    }

    // pause: 마지막 flush 가 곧 마지막 문장이므로 ready_to_stop 을 기다린다.
    set({ phase: 'stopping', stopIntent: 'pause' });
    flushTimer = clearTimer(flushTimer);
    flushTimer = setTimeout(() => {
      if (get().phase !== 'stopping') return;
      // 서버가 응답하지 않아도 버튼이 영구히 잠기지 않도록 강제 종료한다.
      absorbTail(set, get);
      try {
        get().ws?.close();
      } catch {
        /* noop */
      }
      set({ phase: 'paused', stopIntent: null, ws: null, isFinalizing: true });
    }, STOP_FLUSH_TIMEOUT_MS);
  },

  resetTranscript: () => {
    set({
      phase: 'idle',
      serverLines: [],
      finalizedHistory: new Map(),
      committedLines: [],
      volatile: { ...EMPTY_VOLATILE },
      isFinalizing: false,
      pendingResume: null,
      lastSeq: 0,
      desyncCount: 0,
      lastError: null,
    });
  },

  failSession: (reason) => {
    const message =
      reason instanceof Error
        ? reason.message
        : typeof reason === 'string'
          ? reason
          : '알 수 없는 오류가 발생했습니다.';
    set({ phase: 'error', lastError: message });
  },

  checkBackend: async () => {
    try {
      await getHealth();
      set({ backendStatus: 'healthy' });
    } catch {
      set({ backendStatus: 'unhealthy' });
    }
  },

  // ── 메시지 디스패치 ────────────────────────────────────────────────────────
  handleMessage: (raw) => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return;
    }
    const c = classify(parsed);

    switch (c.kind) {
      case 'config': {
        const protocol = c.msg.protocol ?? c.msg.mode ?? 'full';
        if (protocol !== 'delta') {
          // delta 를 요청했는데 full 이 돌아왔다 = 구버전 서버이거나 파라미터 유실.
          // 디스패처가 두 형태를 모두 처리하므로 동작에는 문제가 없다 — 경고만 남긴다.
          console.warn(`[stt] delta 를 요청했으나 서버 적용 프로토콜 = ${protocol}`);
        }
        set({
          protocol,
          useAudioWorklet: Boolean(c.msg.useAudioWorklet),
          appliedLanguage: c.msg.language ?? null,
        });
        configDeferred?.resolve();
        configDeferred = null;
        return;
      }

      case 'ready_to_stop': {
        if (get().stopIntent !== 'pause') return; // fullstop 후 늦게 온 것은 무시
        flushTimer = clearTimer(flushTimer);
        absorbTail(set, get);
        set({ isFinalizing: true });
        try {
          get().ws?.close();
        } catch {
          /* noop */
        }
        return;
      }

      case 'delta': {
        const msg = c.msg as SnapshotMessage | DiffMessage;
        const { lines, desync } = reconstructLines(get().serverLines, msg);
        // 화면이 비지 않도록 재구성 결과를 먼저 반영하고, 그 다음 재동기한다.
        applyState(set, get, lines, msg, msg.seq);
        if (desync) {
          console.warn(
            `[delta] 동기화 불일치: 재구성 ${lines.length}줄 != n_lines ${
              (msg as DiffMessage).n_lines
            } (seq=${msg.seq})`,
          );
          const next = get().desyncCount + 1;
          set({ desyncCount: next });
          if (next > MAX_DESYNC) {
            // 반복되면 blip 이 아니라 프로토콜 버그다. 재시도를 멈추고 사용자에게 알린다.
            set({ lastError: '전사 동기화 오류가 반복됩니다. 다시 시작해 주세요.' });
            return;
          }
          try {
            get().ws?.close();
          } catch {
            /* noop */
          }
          set({ pendingResume: { reason: 'desync', attempt: 0 } });
        }
        return;
      }

      case 'full':
        // full 모드 상태 메시지 = type 필드 자체가 없다. 매번 lines 통째 교체.
        applyState(set, get, Array.isArray(c.msg.lines) ? c.msg.lines : [], c.msg, get().lastSeq);
        return;

      case 'unknown':
        if (import.meta.env.DEV) console.warn(`[stt] 미지의 메시지 type=${c.type}`);
        return;
    }
  },

  _onClose: (e) => {
    const phase = get().phase;
    set({ ws: null });

    if (phase === 'stopping') {
      // 정상 종료 경로 (ready_to_stop 처리 후 close, 또는 flush 중 소켓 사망 — 결과는 같다)
      flushTimer = clearTimer(flushTimer);
      absorbTail(set, get);
      set({ phase: 'paused', stopIntent: null, isFinalizing: true });
      return;
    }

    if (phase === 'connecting') {
      configTimer = clearTimer(configTimer);
      configDeferred?.reject(new Error(`연결 실패 (code ${e.code})`));
      configDeferred = null;
      set({ phase: 'error', lastError: `연결에 실패했습니다 (code ${e.code})` });
      return;
    }

    if (phase === 'recording') {
      // 예상치 못한 끊김 — 전사는 유지하고 자동 재개 대상으로 표시한다.
      set((prev) => ({
        phase: 'paused',
        lastError: `연결이 끊겼습니다 (code ${e.code})`,
        pendingResume: { reason: 'disconnect', attempt: (prev.pendingResume?.attempt ?? 0) + 1 },
      }));
      return;
    }

    if (phase !== 'error' && phase !== 'idle') set({ phase: 'paused' });
  },
}));

// ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

type SetFn = (partial: Partial<SttStore> | ((s: SttStore) => Partial<SttStore>)) => void;
type GetFn = () => SttStore;

/**
 * 상태 메시지 적용. 확정 줄을 이력에 누적하고 volatile 을 통째 교체한다.
 *
 * finalizedHistory 는 **실제로 바뀐 게 있을 때만** 새 Map 을 만든다 — 참조가 매 메시지(50ms)
 * 바뀌면 화면 파생 useMemo 가 전부 무효화되어 델타의 렌더 이득이 사라진다.
 */
function applyState(set: SetFn, get: GetFn, lines: Segment[], v: VolatileState, seq: number): void {
  const s = get();

  let history = s.finalizedHistory;
  let dirty = false;
  for (const ln of lines) {
    if (!isFinalized(ln) || !isRenderable(ln)) continue;
    const k = lineKey(ln);
    const prev = history.get(k);
    if (prev && sameSegment(prev, ln)) continue;
    if (!dirty) {
      history = new Map(history);
      dirty = true;
    }
    history.set(k, ln);
  }

  set({
    serverLines: lines,
    finalizedHistory: dirty ? history : s.finalizedHistory,
    // status:'no_audio_detected' 는 침묵 중 정상적으로 반복된다.
    // 여기서 누적 상태를 비우면 침묵마다 자막이 영구 소실된다 — volatile 만 갈아끼운다.
    volatile: {
      status: v.status,
      buffer_transcription: v.buffer_transcription ?? '',
      buffer_diarization: v.buffer_diarization ?? '',
      buffer_translation: v.buffer_translation ?? '',
      remaining_time_transcription: v.remaining_time_transcription ?? 0,
      remaining_time_diarization: v.remaining_time_diarization ?? 0,
      error: v.error,
    },
    lastSeq: seq,
    lastError: v.error ?? s.lastError,
  });
}

/**
 * 세션을 동결하기 전에 미확정 줄을 확정 이력으로 흡수한다.
 *
 * committedLines 는 finalizedHistory 에서만 채워지므로, 이 처리가 없으면 일시중단 시점에
 * 아직 finalized=false 인 마지막 문장이 통째로 사라진다. EOS flush 가 보통 전부 확정해 주지만
 * '보통'은 '항상'이 아니고, 마지막 문장이 날아가는 건 바로 눈에 띈다.
 */
function absorbTail(set: SetFn, get: GetFn): void {
  const s = get();
  if (s.serverLines.length === 0) return;

  const history = new Map(s.finalizedHistory);
  for (const ln of s.serverLines) {
    if (!isRenderable(ln)) continue;
    history.set(lineKey(ln), { ...ln, finalized: true });
  }
  set({ finalizedHistory: history });
}

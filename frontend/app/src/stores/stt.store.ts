/**
 * @fileoverview STT WebSocket 상태 관리 — Zustand store (whisperlivekit wlk 프로토콜)
 */
import { create } from 'zustand';
import type { LineEntry, RecordFlow, WsControlMessage, WsStateSnapshot, WsSegment } from '@/types/stt';
import { getHealth } from '@/api/health';

// === 상태 타입 ===

export type ConnectionStatus = 'connecting' | 'connected' | 'closed' | 'error';
export type BackendStatus = 'unknown' | 'healthy' | 'unhealthy';

// === Store ===

type STTStore = {
  ws: WebSocket | null;
  connectionStatus: ConnectionStatus;
  recordFlow: RecordFlow;
  url: string | null;

  // finalized history (프론트 누적 — 서버는 5분 슬라이딩 윈도우만 유지)
  finalizedHistory: LineEntry[];
  // 현재 스냅샷의 lines[] (미확정 포함 매번 교체)
  currentLines: WsSegment[];
  // buffer 필드들
  bufferTranscription: string;
  bufferDiarization: string;
  bufferTranslation: string;
  // 상태·오류
  status: WsStateSnapshot['status'];
  error: string | null;
  // config 결과
  useAudioWorklet: boolean;
  // config 수신 여부 (녹음 시작 전 대기용)
  configReceived: boolean;
  // 재연결 횟수
  reconnectAttempts: number;
  // 사용자 수동切断 여부 (재연결 방지용)
  userDisconnected: boolean;
  // 서버 측에서 close 보낼 것임 (재연결 방지용)
  expectServerClose: boolean;
  // 백엔드 헬스 상태
  backendStatus: BackendStatus;
  lastHttpStatus: number | null;

  // 액션
  setRecordFlow: (rf: RecordFlow) => void;
  pauseRecording: () => void;
  resumeRecording: () => void;
  setBackendStatus: (s: BackendStatus) => void;
  connect: (url: string, language?: 'KOR' | 'ENG' | 'AUTO') => void;
  disconnect: () => void;
  sendAudioChunk: (audio: Blob) => void;
  stopRecording: () => void;
  init: () => void;
  handleMessage: (data: string) => void;
  checkBackend: () => Promise<void>;
};

const RECONNECT_DELAY_MS = 1_000;
const MAX_RECONNECT = 5;

export const useSTTStore = create<STTStore>()((set, get) => ({
  ws: null,
  connectionStatus: 'closed',
  recordFlow: 'idle',
  url: null,
  finalizedHistory: [],
  currentLines: [],
  bufferTranscription: '',
  bufferDiarization: '',
  bufferTranslation: '',
  status: undefined,
  error: null,
  useAudioWorklet: false,
  configReceived: false,
  reconnectAttempts: 0,
  userDisconnected: false,
  expectServerClose: false,
  backendStatus: 'unknown',
  lastHttpStatus: null,

  setRecordFlow: (rf) => set({ recordFlow: rf }),

  pauseRecording: () => {
    set({ recordFlow: 'paused' });
  },

  resumeRecording: () => {
    set({ recordFlow: 'recording' });
  },

  setBackendStatus: (s) => set({ backendStatus: s }),
  setLastHttpStatus: (s: number | null) => set({ lastHttpStatus: s }),

  // === WebSocket 연동 ===

  connect: (url: string, language?: 'KOR' | 'ENG' | 'AUTO') => {
    const current = get().ws;
    if (current && current.readyState === WebSocket.OPEN) return;

    // 언어 → 쿼리 파라미터 (§2.1)
    const langParam = language && language !== 'AUTO' ? `?language=${language.toLowerCase()}` : '';
    const wsUrl = `${url}${langParam}`;

    set({ connectionStatus: 'connecting', url: wsUrl, recordFlow: 'connecting', error: null });

    const ws = new WebSocket(wsUrl);

    ws.addEventListener('open', () => {
      // 연결 ≠ 녹음 — recordFlow는 idle 유지
      set({ ws, connectionStatus: 'connected', recordFlow: 'idle' });
    });

    ws.addEventListener('close', (e) => {
      const flow = get().recordFlow;
      const expectServerClose = get().expectServerClose;

      // 서버가 의도적으로 close (stopRecording → 서버 close 또는 stopping flow)
      if (flow === 'stopping' || expectServerClose) {
        set({ ws: null, connectionStatus: 'closed', recordFlow: 'idle', expectServerClose: false });
        return;
      }

      // 사용자 수동切断이면 재연결 안 함
      if (get().userDisconnected) {
        set({ ws: null, connectionStatus: 'closed', recordFlow: 'idle' });
        return;
      }

      // 예상치 못한 닫힘 → idle로
      set({ ws: null, connectionStatus: 'closed', recordFlow: 'idle' });

      // 비정상 종료 → 재연결 시도
      const { reconnectAttempts } = get();
      if ((reconnectAttempts ?? 0) < MAX_RECONNECT) {
        set({ reconnectAttempts: (reconnectAttempts ?? 0) + 1 });
        setTimeout(() => get().connect(url), RECONNECT_DELAY_MS);
      }
    });

    ws.addEventListener('error', () => {
      set({ connectionStatus: 'error' });
    });

    ws.addEventListener('message', (e) => {
      if (typeof e.data === 'string') get().handleMessage(e.data);
    });

    set({ ws });
  },

  disconnect: () => {
    const ws = get().ws;
    if (ws) ws.close();
    set({ ws: null, connectionStatus: 'closed', recordFlow: 'idle', userDisconnected: true });
  },

  // 오디오 청크 전송 (MediaRecorder Blob)
  sendAudioChunk: (audio: Blob) => {
    const { ws } = get();
    if (!ws || ws.readyState !== ws.OPEN) return;
    ws.send(audio);
  },

  // 녹음 종료: 빈 프레임 전송 + 서버 close 예상 플래그
  stopRecording: () => {
    const { ws } = get();
    if (!ws || ws.readyState !== ws.OPEN) return;
    set({ expectServerClose: true });
    ws.send(new ArrayBuffer(0));
    // ready_to_stop 수신 시 idle로 전환 (handleMessage에서 처리)
    // 서버가 close 시 expectServerClose=true → 재연결 없이 정리만
  },

  // === 상태 초기화 (새 녹음 시작 시 호출) ===
  init: () =>
    set({
      recordFlow: 'idle',
      error: null,
      finalizedHistory: [],
      currentLines: [],
      bufferTranscription: '',
      bufferDiarization: '',
      bufferTranslation: '',
      status: undefined,
      configReceived: false,
      reconnectAttempts: 0,
      userDisconnected: false,
      expectServerClose: false,
    }),

  // === 헬스체크 ===
  checkBackend: async () => {
    try {
      await getHealth();
      set({ backendStatus: 'healthy', lastHttpStatus: null });
    } catch (e) {
      const status = (e as Error & { status?: number }).status ?? null;
      set({ backendStatus: 'unhealthy', lastHttpStatus: status });
    }
  },

  // === 메시지 핸들링 ===
  handleMessage: (data: string) => {
    let parsed: WsControlMessage | WsStateSnapshot;
    try {
      parsed = JSON.parse(data);
    } catch {
      return;
    }

    // ── 제어 메시지 (type 있음) ──
    if (typeof parsed.type === 'string') {
      if (parsed.type === 'config') {
        set({ useAudioWorklet: parsed.useAudioWorklet, configReceived: true });
        return;
      }
      if (parsed.type === 'ready_to_stop') {
        // 녹음 종료 확인 — WS는 유지
        set({ recordFlow: 'idle', expectServerClose: false });
        return;
      }
      return;
    }

    // ── 상태 스냅샷 (type 없음) — lines 검증 + 단일 set으로 통합 ──
    const snap = parsed as WsStateSnapshot;
    if (!Array.isArray(snap.lines)) {
      snap.lines = [];
    }
    const finalizedInSnap = snap.lines.filter(
      (l) => l.finalized === true || l.completed === true,
    );

    const historyMap = new Map<string, LineEntry>();
    for (const entry of get().finalizedHistory) {
      historyMap.set(entry.key, entry);
    }
    for (const seg of finalizedInSnap) {
      if (!seg.text || seg.speaker === -2) continue;
      const key = [seg.start, seg.end, seg.speaker].filter(Boolean).join('|');
      if (!key) continue;
      historyMap.set(key, {
        key,
        speaker: seg.speaker ?? 1,
        text: seg.text,
        translation: seg.translation,
        start: seg.start ?? '',
        end: seg.end ?? '',
      });
    }

    set({
      currentLines: snap.lines,
      bufferTranscription: snap.buffer_transcription ?? '',
      bufferDiarization: snap.buffer_diarization ?? '',
      bufferTranslation: snap.buffer_translation ?? '',
      status: snap.status,
      error: snap.error ?? null,
      finalizedHistory: Array.from(historyMap.values()),
    });
  },
}));

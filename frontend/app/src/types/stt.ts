/**
 * @fileoverview wlk WebSocket 계약 타입 — 정본은 docs/API_SPEC.md §2.4, docs/DELTA_PROTOCOL_SPEC.md.
 *
 * 서버측 구현 대조 지점:
 *   whisperlivekit/timed_objects.py  Segment.to_dict() / FrontData.to_dict()
 *   whisperlivekit/diff_protocol.py  DiffTracker.to_message()
 *   whisperlivekit/basic_server.py   /asr 쿼리 파라미터·config 메시지
 */

// ── 세션 파라미터 ────────────────────────────────────────────────────────────

/**
 * 세션 소스 언어. 서버 허용값은 정확히 {auto, ko, en} 이다
 * (basic_server.py `_ALLOWED_SESSION_LANGUAGES`).
 * ⚠️ 'kor'/'eng' 3글자 코드는 코드베이스에 없다 — 보내면 서버가 경고 후 무시하고 기본값을 쓴다.
 */
export type SourceLanguage = 'auto' | 'ko' | 'en';

/** 전송 프로토콜. 'diff' 는 서버측 하위호환 별칭이므로 클라이언트는 'delta' 만 쓴다. */
export type WsMode = 'delta' | 'full';

/** UI 라벨 ↔ 서버 값 매핑. 드롭다운은 약어를 보여주되 서버엔 ISO 639-1 을 보낸다. */
export const LANGUAGE_OPTIONS: ReadonlyArray<{ value: SourceLanguage; label: string }> = [
  { value: 'auto', label: 'AUTO' },
  { value: 'ko', label: 'KOR' },
  { value: 'en', label: 'ENG' },
];

// ── 세션 상태 머신 ───────────────────────────────────────────────────────────

/**
 * 서버 불변식: **WS 연결 1개 = 세션 1개**. 빈 프레임(0바이트)을 보내면 그 세션은 끝나고
 * 같은 연결로는 다시 전사할 수 없다(audio_processor.py `is_stopping` 은 재무장 경로가 없다).
 * 따라서 '재시작'은 항상 새 WebSocket 이다 — 'stopped' 를 따로 두지 않고 idle 로 접는다.
 */
export type SttPhase =
  | 'idle' // 세션 없음. 전사 기록도 비어 있다.
  | 'connecting' // 소켓 열고 config 대기 중
  | 'recording' // 오디오 송신 중
  | 'stopping' // EOS 보내고 서버 flush(ready_to_stop) 대기 중
  | 'paused' // 세션 종료됨. 전사 기록은 committedLines 로 동결돼 화면에 남아 있다.
  | 'error';

/** 세션을 끝낸 의도. pause 는 flush 를 기다리고, stop 은 즉시 버린다. */
export type StopIntent = 'pause' | 'stop' | null;

// ── 서버 → 클라이언트 메시지 ─────────────────────────────────────────────────

export type SttStatus = 'active_transcription' | 'no_audio_detected' | 'error';

export type FinalizeTrigger = 'silence' | 'punctuation' | 'language_switch' | 'speaker_change';

/**
 * 전사 세그먼트 1줄. (timed_objects.py `Segment.to_dict()`)
 *
 * ⚠️ dedup / React key 는 **`id` 단독**을 쓴다.
 *    `id` = round(start, 3) 인 세션 상대 초로, 문장이 자라도 변하지 않는 유일한 안정 식별자다.
 *    `text`·`end` 는 세그먼트가 확장되며 계속 바뀌고, `start`/`end` 는 초 해상도 표시 문자열이라
 *    같은 초에 여러 세그먼트가 시작될 수 있다(빠른 화자전환·코드스위칭).
 *    복합키를 쓰면 같은 문장의 절단판이 새 항목으로 쌓인다 — 실제로 그렇게 구현돼 있었다.
 */
export interface Segment {
  /** round(start,3). 세션 상대 초 — 표시용 start/end 와 값이 다르다. 새 세션마다 0부터 다시 시작. */
  id: number | null;
  /** -2 = 침묵 구간, 0 = 화자분할 처리중, 1..N = 화자 번호. 서버는 -1 을 내보내지 않는다. */
  speaker: number;
  /** 침묵 세그먼트(speaker === -2)는 null 이다. */
  text: string | null;
  /** "HH:MM:SS" 벽시계 또는 "H:MM:SS.cc" 상대 — 두 형식 모두 올 수 있다. 표시 전용. */
  start: string;
  end: string;
  finalized: boolean;
  /** finalized 의 React 호환 별칭. 둘 중 하나라도 true 면 확정으로 본다. */
  completed?: boolean;
  /** 항상 존재하지만 null 인 경우가 잦다. */
  finalize_trigger?: FinalizeTrigger | null;
  /** truthy 일 때만 존재. */
  translation?: string;
  /**
   * 확정됐지만 번역 왕복이 아직 안 끝난 상태. **true 일 때만 존재**한다.
   * 번역이 빈값으로 정착한 경우(에코 재시도 실패)는 이 필드가 오지 않으므로,
   * 프론트는 영영 오지 않을 번역을 기다리며 로더를 남기지 않는다.
   */
  translation_pending?: boolean;
  /** truthy 일 때만 존재. */
  detected_language?: string;
  /** detected_language 의 별칭. */
  lang?: string;
}

/**
 * 매 메시지 전체 값으로 오는 필드들. **병합하지 않고 통째로 교체**한다.
 * (delta 의 diff 메시지에도 전부 실려 온다 — 누적 대상이 아니다.)
 */
export interface VolatileState {
  status?: SttStatus;
  buffer_transcription: string;
  buffer_diarization: string;
  buffer_translation: string;
  remaining_time_transcription: number;
  remaining_time_diarization: number;
  /** truthy 일 때만 존재. */
  error?: string;
}

/** full 모드 상태 메시지 = `type` 필드가 **아예 없다**. 이것이 제어 메시지와의 구분 기준이다. */
export interface FullState extends VolatileState {
  lines: Segment[];
}

/** delta 모드 첫 상태 메시지 (연결당 1회, seq=1). */
export type SnapshotMessage = { type: 'snapshot'; seq: number } & FullState;

/**
 * delta 모드 이후 상태 메시지. **`lines` 를 싣지 않는다.**
 * `new_lines` 는 "새로 추가된 줄"이 아니라 **공통 prefix 이후의 꼬리 전체**다 — deltaProtocol.ts 참조.
 */
export type DiffMessage = {
  type: 'diff';
  seq: number;
  /** 이 메시지를 적용한 **후** 가져야 할 총 줄 수. 검증 기준. */
  n_lines: number;
  /** 앞에서 잘려나간 줄 수. 없으면 0. 가장 먼저 적용한다. */
  lines_pruned?: number;
  /** 없으면 줄 변경 없음. */
  new_lines?: Segment[];
} & VolatileState;

/** 연결 직후 1회. create_tasks() 이전에 전송되므로 반드시 첫 프레임이다. */
export interface ConfigMessage {
  type: 'config';
  /** 서버 --pcm-input 여부. true 면 raw PCM(16kHz s16le), false 면 WebM/Opus 를 보낸다. */
  useAudioWorklet: boolean;
  /** **실제 적용된** 프로토콜. 요청한 mode 가 거부됐는지 이걸로 확인한다. */
  protocol?: WsMode;
  /** protocol 의 레거시 별칭. */
  mode?: WsMode;
  /** 실제 적용된 세션 언어. */
  language?: SourceLanguage;
}

export interface ReadyToStopMessage {
  type: 'ready_to_stop';
}

// ── REST ─────────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: 'ok';
  backend: string | null;
  ready: boolean;
}

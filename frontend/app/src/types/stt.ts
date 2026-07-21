/**
 * @fileoverview STT 관련 타입 정의 — whisperlivekit(wlk) 프로토콜 기반
 */

// === wlk WebSocket Incoming Message ===

export type RecordFlow = 'idle' | 'connecting' | 'recording' | 'paused' | 'stopping';

export interface LineEntry {
    key: string;            // start|end|speaker 복합키
    speaker: number;
    text: string;
    translation?: string;
    start: string;
    end: string;
}

export type WsControlMessage = WsConfig | WsReadyToStop;

export interface WsConfig {
    type: 'config';
    useAudioWorklet: boolean;
    mode?: 'full' | 'diff';
    language?: 'KOR' | 'ENG' | 'AUTO';
}

export interface WsReadyToStop {
    type: 'ready_to_stop';
}

export type WsStateSnapshot = {
    status?: 'active_transcription' | 'no_audio_detected' | 'error';
    lines?: WsSegment[];
    buffer_transcription?: string;
    buffer_diarization?: string;
    buffer_translation?: string;
    remaining_time_transcription?: number;
    remaining_time_diarization?: number;
    error?: string;
};

export interface WsSegment {
    speaker?: number;
    text?: string | null;
    start?: string;
    end?: string;
    finalized?: boolean;
    completed?: boolean;           // finalized 호환 별칭
    finalize_trigger?: 'silence' | 'punctuation' | 'language_switch' | 'speaker_change';
    translation?: string;
    detected_language?: string;
    lang?: string;                 // detected_language 호환 별칭
}

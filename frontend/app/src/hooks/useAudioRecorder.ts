/**
 * @fileoverview 마이크 캡처 + WebM 인코딩.
 *
 * 라이프사이클을 4단계로 쪼갠 이유: 세션 경계에서 **인코더만** 재시작해야 하기 때문이다.
 *
 * ⚠️ 세션마다 반드시 `new MediaRecorder` 를 만든다.
 *    MediaRecorder(audio/webm)는 EBML/WebM 헤더를 **첫 blob 에만** 싣고 이후는 raw 클러스터만
 *    내보낸다. 새 WS 세션은 서버에서 새 FFmpeg 디코더를 띄우므로, 기존 레코더를 그대로 이어
 *    쓰면 헤더 없는 클러스터를 먹여 **에러도 close 도 없이 영구 무출력**이 된다
 *    (소켓은 열려 있고 화면만 멈춘 것처럼 보여 원인 추적이 어렵다).
 *
 * PCM/AudioWorklet 경로는 서버 --pcm-input 일 때만 필요하다. 배포는 기본값(WebM)이라 미구현 —
 * config.useAudioWorklet 이 true 로 오면 호출측이 경고한다.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

/** 서버가 200ms 단위로 처리하므로 100ms 청크면 충분히 촘촘하다. */
const TIMESLICE_MS = 100;

/**
 * getUserMedia 실패를 "무엇을 해야 하는가"가 담긴 한국어 문장으로 바꾼다.
 *
 * 폐쇄망 배포 PC 에서 실제로 겪은 실패가 전부 여기로 모인다 — 권한 프롬프트를 놓쳤거나,
 * 브라우저가 사이트별로 기억해 둔 마이크가 이미 사라진 장치이거나(VBCable 재설치 등),
 * 다른 앱이 장치를 독점한 경우. 원문 DOMException 메시지로는 구분이 안 된다.
 */
export function micErrorMessage(e: unknown): string {
  const name = e instanceof DOMException ? e.name : '';
  switch (name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return '마이크 권한이 거부되었습니다. 주소창의 자물쇠 아이콘에서 마이크를 허용해 주세요.';
    case 'NotFoundError':
    case 'OverconstrainedError':
      return '마이크 장치를 찾을 수 없습니다. Windows 소리 설정에서 입력 장치를 확인해 주세요.';
    case 'NotReadableError':
      return '마이크를 사용할 수 없습니다. 다른 프로그램이 장치를 점유하고 있는지 확인해 주세요.';
    default:
      return `마이크를 열지 못했습니다: ${e instanceof Error ? e.message : String(e)}`;
  }
}

export interface AudioRecorderApi {
  /** 파형 시각화용. teardown 하면 null 이 된다. */
  analyser: AnalyserNode | null;
  /** 마이크 스트림이 살아 있는가 (자동 재개 가능 여부 판단). */
  hasStream: () => boolean;
  /** getUserMedia + AudioContext + analyser. 마이크 권한 프롬프트가 여기서 뜬다. */
  prepare: () => Promise<void>;
  /** 새 MediaRecorder 생성 후 송신 시작. 반드시 config 수신 이후에 호출한다. */
  startEncoder: () => void;
  /** 인코더만 정지. 스트림/analyser 는 유지해 즉시 재개할 수 있게 둔다. */
  stopEncoder: () => void;
  /** 스트림·AudioContext 까지 완전 해제 (OS 마이크 표시등도 꺼진다). */
  teardown: () => void;
}

export function useAudioRecorder(onChunk: (data: Blob) => void): AudioRecorderApi {
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const onChunkRef = useRef(onChunk);
  /**
   * 인코더 세대. stop() 은 마지막 ondataavailable 을 한 번 더 발화시키는데, 그 꼬리 blob 이
   * 다음 세션 소켓으로 새어 들어가면 새 스트림의 헤더 순서를 망가뜨린다.
   */
  const encoderGenRef = useRef(0);

  useEffect(() => {
    onChunkRef.current = onChunk;
  }, [onChunk]);

  const hasStream = useCallback(() => streamRef.current !== null, []);

  const prepare = useCallback(async () => {
    if (streamRef.current) return; // 이미 준비됨 — 권한 프롬프트를 반복하지 않는다

    if (!navigator?.mediaDevices?.getUserMedia) {
      throw new Error('이 브라우저는 오디오 녹음을 지원하지 않습니다.');
    }

    // STT 전처리와 충돌하지 않도록 브라우저측 오디오 가공은 전부 끈다.
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
    } catch (e) {
      // DOMException 원문("Permission denied")은 화면에 띄워봐야 무엇을 해야 할지 알 수 없다.
      throw new Error(micErrorMessage(e));
    }
    streamRef.current = stream;

    const ctx = new AudioContext();
    audioContextRef.current = ctx;
    if (ctx.state === 'suspended') await ctx.resume();

    const node = ctx.createAnalyser();
    node.fftSize = 2048;
    ctx.createMediaStreamSource(stream).connect(node);
    setAnalyser(node);
  }, []);

  const stopEncoder = useCallback(() => {
    encoderGenRef.current += 1; // 꼬리 blob 무효화
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') recorder.stop();
    recorderRef.current = null;
  }, []);

  const startEncoder = useCallback(() => {
    const stream = streamRef.current;
    if (!stream) throw new Error('마이크가 준비되지 않았습니다.');

    stopEncoder(); // 남아 있는 인코더 정리 + 세대 증가

    const gen = encoderGenRef.current;

    const mimeType = 'audio/webm';
    let recorder: MediaRecorder;
    if (
      typeof MediaRecorder.isTypeSupported === 'function' &&
      MediaRecorder.isTypeSupported(mimeType)
    ) {
      recorder = new MediaRecorder(stream, { mimeType });
    } else {
      // 서버 FFmpeg 가 디코딩하지 못할 컨테이너일 수 있다 — 조용히 넘어가지 않는다.
      console.warn(`[audio] ${mimeType} 미지원 — 브라우저 기본 컨테이너로 대체합니다.`);
      recorder = new MediaRecorder(stream);
    }
    recorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (gen !== encoderGenRef.current) return; // 이전 세대의 꼬리 blob
      if (e.data.size > 0) onChunkRef.current(e.data);
    };

    // ⚠️ timeslice 필수 — 인자 없이 start() 하면 stop() 시점까지 청크가 나오지 않는다.
    recorder.start(TIMESLICE_MS);
  }, [stopEncoder]);

  const teardown = useCallback(() => {
    stopEncoder();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    const ctx = audioContextRef.current;
    // 이미 닫힌 컨텍스트에 close() 하면 reject 된다 (예전엔 endRecording 과 언마운트에서 이중 호출).
    if (ctx && ctx.state !== 'closed') void ctx.close();
    audioContextRef.current = null;
    setAnalyser(null);
  }, [stopEncoder]);

  // 언마운트 정리
  useEffect(() => teardown, [teardown]);

  return { analyser, hasStream, prepare, startEncoder, stopEncoder, teardown };
}

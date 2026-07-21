/**
 * @fileoverview 오디오 녹음 훅 (MediaRecorder/WebM) — whisperlivekit wlk 프로토콜
 *
 * ⚠️ AudioWorklet/PCM 경로는 서버 --pcm-input 시 필요.
 * 기본 배포에서는 --pcm-input 미지정이므로 MediaRecorder/WebM 만 구현.
 */
import { useSTTStore } from '@/stores/stt.store';
import { useCallback, useEffect, useRef, useState } from 'react';

export const useAudioRecorder = (onDataAvailable: (data: Blob) => void) => {
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);
  const recordFlow = useSTTStore((s) => s.recordFlow);
  const recordFlowRef = useRef(recordFlow);
  useEffect(() => {
    recordFlowRef.current = recordFlow;
  }, [recordFlow]);

  const streamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);

  const startRecording = useCallback(async () => {
    if (!navigator?.mediaDevices?.getUserMedia) {
      throw new Error('이 브라우저는 오디오 녹음을 지원하지 않습니다.');
    }
    // WS 연결 대기 — config 메시지 없이도 녹음 시작 가능
    const ws = useSTTStore.getState().ws;
    console.log('[audio] ws readyState =', ws?.readyState, 'OPEN =', WebSocket.OPEN);
    if (ws?.readyState !== WebSocket.OPEN) {
      console.log('[audio] WS not open, waiting...');
      await new Promise<void>((resolve) => {
        const check = () => {
          if (useSTTStore.getState().ws?.readyState === WebSocket.OPEN) {
            console.log('[audio] WS now open');
            resolve();
          } else {
            setTimeout(check, 50);
          }
        };
        check();
      });
    }

    try {
      console.log('[audio] requesting getUserMedia...');
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });
      console.log('[audio] getUserMedia success, tracks:', stream.getTracks().map((t) => `${t.label} (${t.readyState})`).join(', '));
      streamRef.current = stream;

      // analyser for waveform — AudioContext 재사용 + suspended resume
      if (!audioContextRef.current) {
        const ctx = new AudioContext();
        audioContextRef.current = ctx;
        if (ctx.state === 'suspended') {
          await ctx.resume();
        }
      }
      const audioContext = audioContextRef.current;
      const source = audioContext.createMediaStreamSource(stream);
      const analyserNode = audioContext.createAnalyser();
      analyserNode.fftSize = 2048;
      source.connect(analyserNode);
      setAnalyser(analyserNode);
      analyserRef.current = analyserNode;

      // MediaRecorder — WebM (100ms timeslice 필수)
      const mimeType = 'audio/webm';
      let recorder: MediaRecorder;
      try {
        recorder = new MediaRecorder(stream, { mimeType });
      } catch {
        // Safari 등 audio/webm 미지원 → fallback
        recorder = new MediaRecorder(stream);
      }
      console.log('[audio] MediaRecorder state:', recorder.state, 'mimeType:', recorder.mimeType);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        console.log('[audio] ondataavailable size =', e.data.size, 'flowRef =', recordFlowRef.current);
        if (recordFlowRef.current === 'recording' && e.data.size > 0) {
          onDataAvailable(e.data);
        }
      };

      // ⚠️ timeslice 반드시 지정 — 인자 없으면 stop() 시점까지 청크 안 나옴
      recorder.start(100);
      console.log('[audio] recorder.start(100) called');
    } catch (error) {
      console.error('음성 인식 시작 실패:', error);
      throw error;
    }
  }, [onDataAvailable]);



  const endRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder?.state !== 'inactive') {
      recorder?.stop();
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    audioContextRef.current?.close();
    audioContextRef.current = null;
    setAnalyser(null);
    analyserRef.current = null;
    streamRef.current = null;
    mediaRecorderRef.current = null;
  }, []);

  // 컴포넌트 언마운트 시 정리
  useEffect(() => {
    return () => {
      const recorder = mediaRecorderRef.current;
      if (recorder?.state !== 'inactive') {
        recorder?.stop();
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
      audioContextRef.current?.close();
    };
  }, []);

  const pauseRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.pause();
    }
  }, []);

  const resumeRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state === 'paused') {
      recorder.resume();
    }
  }, []);

  return { analyser, startRecording, endRecording, pauseRecording, resumeRecording };
};

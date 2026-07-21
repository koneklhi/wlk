/**
 * @fileoverview 세션 오케스트레이션 — 소켓 라이프사이클과 오디오 라이프사이클이 만나는 유일한 곳.
 *
 * 사용자 조작(시작/일시중단/재개/종료)과 자동 복구(끊김·desync)가 전부 여기를 지난다.
 * 저장소(store)는 소켓만, 레코더 훅은 마이크만 알고, 둘의 순서는 여기서만 정한다.
 */
import { useCallback, useEffect } from 'react';
import { MAX_AUTO_RESUME, RESUME_BACKOFF_MS, useSttStore } from '@/stores/stt.store';
import { useAudioRecorder } from '@/hooks/useAudioRecorder';

export function useSttSession() {
  const phase = useSttStore((s) => s.phase);
  const pendingResume = useSttStore((s) => s.pendingResume);
  const useAudioWorklet = useSttStore((s) => s.useAudioWorklet);

  const sendAudioChunk = useSttStore((s) => s.sendAudioChunk);
  // 레코더 API 함수들은 전부 useCallback 으로 identity 가 안정적이라 그대로 의존성에 쓸 수 있다.
  const { analyser, hasStream, prepare, startEncoder, stopEncoder, teardown } =
    useAudioRecorder(sendAudioChunk);

  /**
   * 세션 시작/재개. 순서가 중요하다.
   *
   * ① 마이크 먼저 — 권한이 거부되면 서버 세션을 아예 열지 않는다. 소켓을 먼저 열면
   *    거부 시 FFmpeg 까지 띄운 고아 세션이 남는다(참조 구현은 소켓 우선이라 이 문제가 있다).
   * ② config 수신까지 대기 — 서버가 준비되기 전에 오디오를 보내지 않는다.
   * ③ **새** MediaRecorder 로 송신 시작 — 새 세션엔 WebM 헤더부터 다시 실려야 한다.
   */
  const start = useCallback(
    async (opts: { resume: boolean }) => {
      const store = useSttStore.getState();
      try {
        stopEncoder(); // 재개 시 이전 인코더 확실히 정리
        await prepare(); // ①
        await store.beginSession({ resume: opts.resume }); // ②
        startEncoder(); // ③
        store.markRecording();
      } catch (e) {
        teardown();
        useSttStore.getState().failSession(e);
      }
    },
    [prepare, startEncoder, stopEncoder, teardown],
  );

  /** 시작 버튼. paused 였으면 이어서(누적 전사 유지), idle 이었으면 새로 시작. */
  const startOrResume = useCallback(() => {
    const resume = useSttStore.getState().phase === 'paused';
    return start({ resume });
  }, [start]);

  /**
   * 일시중단. 서버 불변식상 세션이 끝나므로 마이크까지 놓아준다(OS 마이크 표시등 꺼짐).
   * 누적 전사는 store 가 committedLines 로 동결해 화면에 그대로 남긴다.
   */
  const pause = useCallback(() => {
    stopEncoder();
    useSttStore.getState().endSession('pause');
    teardown();
  }, [stopEncoder, teardown]);

  /** 종료. 전사 기록까지 버린다(확인 다이얼로그는 호출측 책임). */
  const stop = useCallback(() => {
    stopEncoder();
    useSttStore.getState().endSession('stop');
    teardown();
  }, [stopEncoder, teardown]);

  /** 기록만 초기화 (세션은 이미 없음). */
  const reset = useCallback(() => {
    useSttStore.getState().resetTranscript();
  }, []);

  // ── 자동 복구 ──────────────────────────────────────────────────────────────
  // 예상치 못한 끊김/desync 는 사용자가 '재개'를 누른 것과 **같은 동작**이다.
  // hasStream() 가드가 핵심: 사용자가 직접 일시중단한 경우엔 스트림이 없으므로 재개하지 않는다.
  useEffect(() => {
    if (!pendingResume || phase !== 'paused') return;
    if (!hasStream()) return;
    if (pendingResume.attempt >= MAX_AUTO_RESUME) return; // 초과 → 사용자 조작 대기

    const delay = RESUME_BACKOFF_MS[Math.min(pendingResume.attempt, RESUME_BACKOFF_MS.length - 1)];
    const t = setTimeout(() => void start({ resume: true }), delay);
    return () => clearTimeout(t);
  }, [phase, pendingResume, start, hasStream]);

  // 서버가 PCM 모드로 떠 있으면 WebM 을 보내봐야 전사가 나오지 않는다. 조용히 실패하지 않도록 경고.
  useEffect(() => {
    if (useAudioWorklet) {
      console.error(
        '[stt] 서버가 --pcm-input 모드입니다. 이 UI 는 WebM 만 전송하므로 전사가 나오지 않습니다.',
      );
    }
  }, [useAudioWorklet]);

  return { analyser, startOrResume, pause, stop, reset };
}

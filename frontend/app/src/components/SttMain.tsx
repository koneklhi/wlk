/**
 * @fileoverview STT 메인 화면 — stt-frontend 스타일 (로고-제목-로고 헤더 + 전사 영역)
 */
import logoAirforce from '@/assets/images/logo-airforce.png';
import logoRight from '@/assets/images/logo-right.png';
import { BackendErrorOverlay } from '@/components/BackendErrorOverlay';
import { SttSettingDrawer } from '@/components/SttSettingDrawer';
import { SttTextViewer } from '@/components/SttTextViewer';
import { STTThemeProvider, useSttTextStyle } from '@/components/SttThemeProvider';
import { Server } from '@/constants';
import { useAudioRecorder } from '@/hooks/useAudioRecorder';
import useSettingSidebarStore from '@/stores/stt-sidebar-store';
import { useSTTStore } from '@/stores/stt.store';
import { useCallback, useEffect, useMemo, useRef } from 'react';

interface ProcessSentence {
  content: string;
  translation?: string;
  status: 'complete' | 'process';
}

function SttMainInner() {
  const systemStyle = useSttTextStyle('system');

  const finalizedHistory = useSTTStore((s) => s.finalizedHistory);
  const currentLines = useSTTStore((s) => s.currentLines);
  const bufferTranscription = useSTTStore((s) => s.bufferTranscription);
  const bufferTranslation = useSTTStore((s) => s.bufferTranslation);
  const recordFlow = useSTTStore((s) => s.recordFlow);
  const connectionStatus = useSTTStore((s) => s.connectionStatus);
  const checkBackend = useSTTStore((s) => s.checkBackend);
  const backendStatus = useSTTStore((s) => s.backendStatus);
  const lastHttpStatus = useSTTStore((s) => s.lastHttpStatus);
  const { connect, sendAudioChunk, setRecordFlow, pauseRecording, resumeRecording, stopRecording } = useSTTStore();

  // 마지막 실제 콘텐츠 DOM 노드 ref — scrollIntoView 타겟
  const lastContentRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (finalizedHistory.length > 0 || currentLines.length > 0 || bufferTranscription) {
      lastContentRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [finalizedHistory.length, currentLines.length, bufferTranscription, bufferTranslation]);

  // ── 초기 헬스체크 + 자동 WebSocket 연결 ──
  useEffect(() => {
    checkBackend();
    const interval = setInterval(checkBackend, 15_000);
    return () => clearInterval(interval);
  }, [checkBackend]);

  useEffect(() => {
    let cancelled = false;
    const attempt = async () => {
      const ws = useSTTStore.getState().ws;
      if (ws?.readyState === WebSocket.OPEN) return;
      useSTTStore.getState().connect(Server.WS_URL, 'AUTO');
      for (let i = 0; i < 3; i++) {
        if (cancelled) return;
        await new Promise((r) => setTimeout(r, 1500));
        const ws2 = useSTTStore.getState().ws;
        if (ws2?.readyState === WebSocket.OPEN) return;
      }
    };
    attempt();
    return () => { cancelled = true; };
  }, []);

  // ── audio recorder ──
  const { analyser, startRecording, endRecording, pauseRecording: recorderPause, resumeRecording: recorderResume } = useAudioRecorder(
    (data) => sendAudioChunk(data),
  );

  // ── wlk → 참조 스타일 매핑 ──
  const isRecording = recordFlow === 'recording';
  const isPaused = recordFlow === 'paused';

  // 완료된 문장 (finalizedHistory) — 번역 포함
  const completedSentences: ProcessSentence[] = useMemo(() => {
    return finalizedHistory.map((entry) => ({
      content: entry.text,
      translation: entry.translation || undefined,
      status: 'complete' as const,
    }));
  }, [finalizedHistory]);

  // 진행 중 문장: 마지막 미확정 currentLine + 버퍼
  const processingSentence: ProcessSentence | null = useMemo(() => {
    const unfinalized = currentLines.filter(
      (seg) => seg.finalized !== true && seg.completed !== true,
    );

    const activeSegment = [...unfinalized]
      .reverse()
      .find((seg) => seg.text && seg.speaker !== -2 && seg.speaker !== 0);

    if (!activeSegment) {
      if (bufferTranscription) {
        return {
          content: bufferTranscription,
          translation: bufferTranslation || undefined,
          status: 'process' as const,
        };
      }
      return null;
    }

    return {
      content: activeSegment.text || '',
      translation: activeSegment.translation || bufferTranslation || undefined,
      status: 'process' as const,
    };
  }, [currentLines, bufferTranscription, bufferTranslation]);

  const isConnecting = connectionStatus === 'connecting';

  // ── 녹음 제어 ──
  const handleStartRecording = useCallback(async () => {
    try {
      await startRecording();
      setRecordFlow('recording');
    } catch {
      console.error('녹음 시작 실패');
    }
  }, [startRecording, setRecordFlow]);

  const handlePauseRecording = useCallback(() => {
    recorderPause();
    pauseRecording();
  }, [recorderPause, pauseRecording]);

  const handleResumeRecording = useCallback(() => {
    recorderResume();
    resumeRecording();
  }, [recorderResume, resumeRecording]);

  const handleConfirmStop = useCallback(() => {
    if (isPaused) {
      handleResumeRecording();
    }
    stopRecording();
    endRecording();
    setRecordFlow('stopping');
  }, [isPaused, handleResumeRecording, stopRecording, endRecording, setRecordFlow]);

  const handleReset = useCallback(() => {
    useSTTStore.getState().init();
  }, []);



  const showTranscript = isRecording || isPaused || finalizedHistory.length > 0;
  const isOpenSidebar = useSettingSidebarStore((s) => s.isOpenSidebar);

  // 마지막 콘텐츠 인덱스 — ref 할당용
  const hasProcessing = !!processingSentence;
  const lastIndex = hasProcessing
    ? completedSentences.length
    : completedSentences.length - 1;

  return (
    <div className="w-full h-full relative flex flex-col">
      {/* ── Header ── */}
      <div
        className="w-full flex justify-center py-0.5 px-2 shadow-2xl items-center shrink-0"
        style={{ backgroundColor: 'var(--stt-title-bg)' }}
      >
        <img
          src={logoAirforce}
          className="mr-2"
          style={{ width: 'var(--stt-image-size-logo)' }}
          alt="공군 로고"
        />
        <div className="flex flex-col">
          <h1
            className="font-bold tracking-[0.07rem]"
            style={{
              fontFamily: 'var(--stt-font)',
              color: 'var(--stt-color-title-fg)',
              fontSize: 'var(--stt-font-size-title)',
            }}
          >
            대한민국 공군 AI 실시간 통역 체계
          </h1>
          <h2
            className="font-semibold -mt-1.5 tracking-[-0.047rem]"
            style={{
              fontFamily: 'var(--stt-font)',
              color: 'var(--stt-color-title-fg)',
              fontSize: 'var(--stt-font-size-subtitle)',
            }}
          >
            Republic of Korea Air Force AI Real-time Translation System
          </h2>
        </div>
        <img
          src={logoRight}
          className="py-2 scale-90"
          style={{ width: 'var(--stt-image-size-logo)' }}
          alt=""
        />
      </div>

      {/* ── Transcript Area ── */}
      <div className="flex-1 h-full">
        {backendStatus === 'unhealthy' && lastHttpStatus === 500 ? (
          <BackendErrorOverlay
            isConnecting={isConnecting}
            onClose={
              connectionStatus === 'closed'
                ? () => useSTTStore.getState().connect(Server.WS_URL, 'AUTO')
                : undefined
            }
            status={lastHttpStatus}
          />
        ) : !showTranscript ? (
          <div className="w-full h-full flex items-center justify-center flex-grow-0">
            <span style={systemStyle}>연결 대기중...</span>
          </div>
        ) : (
          <div
            className="w-full h-full overflow-y-auto pt-8 pb-12 px-16 custom-scrollbar"
            style={isOpenSidebar ? { paddingRight: '512px' } : undefined}
          >
            <div className="flex flex-col gap-14">
              {completedSentences.map((sentence, index) => (
                <div
                  key={`completed-${index}`}
                  ref={index === lastIndex ? lastContentRef : undefined}
                >
                  <SttTextViewer
                    content={sentence.content}
                    translation={sentence.translation}
                    status={sentence.status}
                    index={index}
                  />
                </div>
              ))}
              {processingSentence && (
                <div key="processing" ref={lastContentRef}>
                  <SttTextViewer
                    content={processingSentence.content}
                    translation={processingSentence.translation}
                    status={processingSentence.status}
                    index={completedSentences.length}
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Settings Drawer ── */}
      <SttSettingDrawer
        recordFlow={recordFlow}
        analyser={analyser}
        startRecording={handleStartRecording}
        onPauseRecording={handlePauseRecording}
        onResumeRecording={handleResumeRecording}
        onStopRecording={handleConfirmStop}
        onReset={handleReset}
      />
    </div>
  );
}

export function SttMain() {
  return (
    <STTThemeProvider>
      <SttMainInner />
    </STTThemeProvider>
  );
}

/**
 * @fileoverview STT 메인 화면 — stt-frontend 스타일 (로고-제목-로고 헤더 + 전사 영역)
 *
 * 화면 구성은 기존 배포 UI 그대로다. 바뀐 것은 데이터 출처뿐 —
 * 세션 제어는 useSttSession() 이 담당하고 여기는 렌더만 한다.
 *
 * 마운트 시 자동 연결은 하지 않는다: 연결 = 서버 세션 생성(FFmpeg + 파이프라인 기동)이라
 * 아무도 녹음하지 않는 페이지 로드마다 고아 세션이 생긴다.
 */
import logoAirforce from '@/assets/images/logo-airforce.png';
import logoRight from '@/assets/images/logo-right.png';
import { BackendErrorOverlay } from '@/components/BackendErrorOverlay';
import { SttSettingDrawer } from '@/components/SttSettingDrawer';
import { SttTextViewer } from '@/components/SttTextViewer';
import { STTThemeProvider, useSttTextStyle } from '@/components/SttThemeProvider';
import { useSttSession } from '@/hooks/useSttSession';
import { useTranscriptRows } from '@/hooks/useTranscriptRows';
import useSettingSidebarStore from '@/stores/stt-sidebar-store';
import { useSttStore } from '@/stores/stt.store';
import { useThemeStore } from '@/stores/theme.store';
import { useEffect, useRef } from 'react';
import { toast } from 'react-toastify';

const HEALTH_POLL_MS = 15_000;
/** 이 픽셀 이내로 바닥에 붙어 있을 때만 자동 스크롤한다. */
const AUTOSCROLL_THRESHOLD_PX = 120;

function SttMainInner() {
  const systemStyle = useSttTextStyle('system');
  const showTimestamp = useThemeStore((s) => s.showTimestamp);

  const phase = useSttStore((s) => s.phase);
  const backendStatus = useSttStore((s) => s.backendStatus);
  const checkBackend = useSttStore((s) => s.checkBackend);
  const lastError = useSttStore((s) => s.lastError);
  const errorSeq = useSttStore((s) => s.errorSeq);

  const rows = useTranscriptRows();
  const session = useSttSession();

  const isOpenSidebar = useSettingSidebarStore((s) => s.isOpenSidebar);

  // 목록 끝 sentinel — 행마다 ref 를 갈아끼우지 않고 여기 한 곳만 스크롤 타겟으로 쓴다.
  const endRef = useRef<HTMLDivElement | null>(null);
  const scrollBoxRef = useRef<HTMLDivElement | null>(null);
  // 사용자가 위로 올려 읽는 중인지. '콘텐츠 증가'가 아니라 '사용자의 스크롤 행위'로만 갱신한다.
  const stickToBottomRef = useRef(true);

  // 스크롤 이벤트(사용자 조작)에서만 바닥 고정 여부를 판정한다.
  const handleScroll = () => {
    const box = scrollBoxRef.current;
    if (!box) return;
    stickToBottomRef.current =
      box.scrollHeight - box.scrollTop - box.clientHeight < AUTOSCROLL_THRESHOLD_PX;
  };

  useEffect(() => {
    // 세션 종료 등으로 전사가 비면 '따라가기' 의도를 초기화 — 다음 세션 첫 줄부터 다시 바닥을 따라간다.
    // (사용자가 이전 세션에서 위로 올려 stickToBottomRef 가 false 로 남는 것을 방지.)
    if (rows.length === 0) {
      stickToBottomRef.current = true;
      return;
    }
    // 바닥에 붙어 있던 경우에만 새 전사/번역을 따라간다. 즉시 스크롤로 smooth 피드백 루프 차단.
    if (stickToBottomRef.current) endRef.current?.scrollIntoView({ block: 'end' });
  }, [rows]);

  // 세션 오류를 화면에 내보낸다. 이게 없으면 마이크 권한 거부·연결 실패가 전부
  // "시작을 눌러도 아무 일도 안 일어남" 으로만 보인다(상태점만 빨개진다).
  // errorSeq 를 구독하는 이유는 같은 오류가 연속으로 나도 매번 알리기 위함.
  useEffect(() => {
    if (errorSeq > 0 && lastError) toast.error(lastError, { autoClose: 8000 });
  }, [errorSeq, lastError]);

  // 백엔드 헬스 폴링 (세션과 무관 — 서버가 살아있는지만 본다)
  useEffect(() => {
    void checkBackend();
    const t = setInterval(() => void checkBackend(), HEALTH_POLL_MS);
    return () => clearInterval(t);
  }, [checkBackend]);

  const hasTranscript = rows.length > 0;
  const isConnecting = phase === 'connecting';

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
        {backendStatus === 'unhealthy' && !hasTranscript ? (
          <BackendErrorOverlay isConnecting={isConnecting} onClose={() => void checkBackend()} />
        ) : !hasTranscript ? (
          <div
            className="w-full h-full flex items-center justify-center flex-grow-0"
            data-testid="stt-idle"
          >
            <span style={systemStyle}>{idleMessage(phase)}</span>
          </div>
        ) : (
          <div
            ref={scrollBoxRef}
            onScroll={handleScroll}
            className="w-full h-full overflow-y-auto pt-8 pb-12 px-16 custom-scrollbar"
            style={isOpenSidebar ? { paddingRight: '512px' } : undefined}
          >
            <div className="flex flex-col gap-14" data-testid="stt-transcript">
              {rows.map((row) => (
                // key 는 안정 세그먼트 id 기반 — 배열 index 를 쓰면 백엔드가 최근 줄을
                // 소급 수정할 때 React 가 엉뚱한 DOM 노드를 재사용한다.
                <SttTextViewer key={row.key} row={row} showTimestamp={showTimestamp} />
              ))}
              <div ref={endRef} />
            </div>
          </div>
        )}
      </div>

      {/* ── Settings Drawer ── */}
      <SttSettingDrawer
        analyser={session.analyser}
        onStart={session.startOrResume}
        onPause={session.pause}
        onStop={session.stop}
        onReset={session.reset}
      />
    </div>
  );
}

/** 전사가 없을 때의 안내 문구. 자동 연결을 하지 않으므로 '연결 대기중'은 더 이상 맞지 않는다. */
function idleMessage(phase: string): string {
  if (phase === 'connecting') return '연결 중...';
  if (phase === 'recording') return '음성 인식 중...';
  return '음성 인식을 시작하면 전사 결과가 여기에 표시됩니다';
}

export function SttMain() {
  return (
    <STTThemeProvider>
      <SttMainInner />
    </STTThemeProvider>
  );
}

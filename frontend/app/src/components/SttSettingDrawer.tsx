/**
 * @fileoverview STT 설정 panel — 오른쪽 slide-in drawer (stt-frontend 평면 스타일)
 *
 * UI 형태는 기존 배포 UI 그대로 유지한다. 바뀐 것은 두 가지뿐:
 *   ① 버튼 활성/비활성을 세션 phase 에서 파생 — 예전에는 자체 boolean 을 봐서 종료 후 먹통이 됐다.
 *   ② 언어 select 가 즉시 재연결하지 않고 값만 저장 — 세션 중 언어 변경은 새 연결이 필요하다.
 * 그리고 기존 행 스타일 그대로 '시각 표시' 행을 추가했다.
 */
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { WaveformVisualizer } from '@/components/WaveformVisualizer';
import { APP_VERSION, BASE_PATH } from '@/constants';
import { useTranscriptRows } from '@/hooks/useTranscriptRows';
import useSettingSidebarStore from '@/stores/stt-sidebar-store';
import { useSttStore } from '@/stores/stt.store';
import { useThemeStore } from '@/stores/theme.store';
import { LANGUAGE_OPTIONS, type SourceLanguage } from '@/types/stt';
import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

/**
 * 녹음 중인데 이 시간이 지나도록 표시할 전사가 한 줄도 없으면 "입력 음성 없음" 으로 알린다.
 *
 * ⚠️ 서버의 `status: "no_audio_detected"` 는 이 판정에 쓸 수 없다. 무음이 이어지면 서버가
 *    침묵 세그먼트(speaker:-2, text:"")를 만들어 `lines` 가 더 이상 비지 않으므로, 그 status
 *    는 세션 첫 스냅샷(seq=1)에만 잠깐 나오고 이후로는 계속 active_transcription 이다
 *    (실측 확인). 그래서 "화면에 내보낼 줄이 하나도 없는가" 를 신호로 쓴다 — 침묵 세그먼트는
 *    transcriptRows 의 isVisible() 이 이미 걸러낸다.
 *
 * 잡아내려는 것은 "연결은 됐는데 마이크에 소리가 아예 안 들어오는" 경우다(권한·장치 오선택).
 * 한 줄이라도 전사된 뒤 도중에 마이크가 죽는 경우는 이 신호로 잡지 못한다 — 그건 발화 중
 * 긴 침묵과 구분되지 않아 오경보가 더 해롭다.
 */
const NO_AUDIO_GRACE_MS = 8_000;

const SELECT_CLASS =
  'h-10 px-3 text-sm bg-background border border-input rounded-md text-foreground outline-none w-[120px] disabled:opacity-50 disabled:cursor-not-allowed';

export const SttSettingDrawer = ({
  analyser,
  onStart,
  onPause,
  onStop,
  onReset,
}: {
  analyser: AnalyserNode | null;
  onStart: () => Promise<void> | void;
  onPause: () => void;
  onStop: () => void;
  onReset: () => void;
}) => {
  const { isOpenSidebar, toggleSidebar } = useSettingSidebarStore();

  const phase = useSttStore((s) => s.phase);
  const backendStatus = useSttStore((s) => s.backendStatus);
  const language = useSttStore((s) => s.language);
  const setLanguage = useSttStore((s) => s.setLanguage);

  const rows = useTranscriptRows();

  // 소리가 안 들어오는 상태를 상태 라벨로 드러낸다. 예전에는 마이크가 엉뚱한 장치로
  // 잡혀도 화면이 '인식 중' 그대로여서 사용자가 원인을 알 길이 없었다.
  const [noAudio, setNoAudio] = useState(false);
  const silent = phase === 'recording' && rows.length === 0;
  useEffect(() => {
    // 세우는 것도 내리는 것도 타이머를 거친다 — effect 본문에서 곧바로 setState 하면
    // 렌더가 연쇄된다(react-hooks/set-state-in-effect).
    const t = setTimeout(() => setNoAudio(silent), silent ? NO_AUDIO_GRACE_MS : 0);
    return () => clearTimeout(t);
  }, [silent]);

  // 소켓을 새로 여는 중(connecting)에만 조작을 막는다.
  //
  // ⚠️ 'stopping'(EOS 보내고 서버 flush 대기)은 **막지 않는다**. flush 는 서버 사정으로 몇 초씩
  //    걸리는데(번역 활성 시 10초 폴백까지 걸리는 것을 실측), 그동안 버튼이 전부 잠겨
  //    "일시중단하면 한참 동안 재개를 못 누른다"가 됐다. 재개는 어차피 **새 소켓**이라
  //    이전 세션의 flush 완료를 기다릴 이유가 없고, 화면 내용은 beginSession 이 동결한다.
  const busy = phase === 'connecting';
  const isPaused = phase === 'paused';
  const isStopping = phase === 'stopping';
  const canStart = !busy && (phase === 'idle' || isPaused || isStopping || phase === 'error');
  const canPauseOrResume = phase === 'recording' || isPaused || isStopping;
  const canStop = phase === 'recording' || isPaused || isStopping;
  const canChangeLanguage = phase === 'idle' || phase === 'error';

  const {
    backgroundColor,
    setBackgroundColor,
    titleBackgroundColor,
    setTitleBackgroundColor,
    fontSizeOriginal,
    setFontSizeOriginal,
    fontSizeTranslation,
    setFontSizeTranslation,
    fontSizeSystem,
    setFontSizeSystem,
    colorOriginalForeground,
    setColorOriginalForeground,
    colorTranslationForeground,
    setColorTranslationForeground,
    colorSystemForeground,
    setColorSystemForeground,
    colorTitleForeground,
    setColorTitleForeground,
    logoSize,
    setLogoSize,
    showTimestamp,
    setShowTimestamp,
  } = useThemeStore();

  const handleResetTheme = useCallback(() => {
    useThemeStore.getState().reset();
  }, []);

  return (
    <>
      {/* sidebar toggle button */}
      {!isOpenSidebar && (
        <div className="fixed h-full right-0 flex items-center pr-2 z-[150]">
          <Button
            size="icon"
            variant="ghost"
            onClick={toggleSidebar}
            aria-label="설정 열기"
            data-testid="stt-settings-toggle"
          >
            <X size={18} />
          </Button>
        </div>
      )}

      {/* drawer */}
      <AnimatePresence initial={false}>
        {isOpenSidebar && (
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: '500px' }}
            exit={{ width: 0 }}
            transition={{ type: 'keyframes', duration: 0.3 }}
            className="h-full z-[200] fixed right-0 top-0 border-l bg-[#11151c]"
          >
            <div className="w-full h-full relative shadow-xl overflow-y-auto bg-[#11151c] text-foreground">
              {/* header */}
              <div className="flex w-full justify-between items-center border-b py-2 px-4">
                <h2 className="text-lg font-semibold">Setting</h2>
                <Button variant="ghost" className="w-4" onClick={toggleSidebar}>
                  <X size={20} />
                </Button>
              </div>

              <div className="w-full flex-1 py-4 pl-4 pr-6 flex flex-col gap-6">
                {/* ── 상태 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base">상태</p>
                  {/* data-phase 는 지역화 문구가 아니라 raw enum 이다 — 경로 C 하니스가 이걸로 폴링한다.
                      문구(phaseLabel)를 바꿔도 자동화가 깨지지 않게 하는 것이 목적이다. */}
                  <div
                    className="flex items-center gap-1.5 text-sm font-mono"
                    data-testid="stt-status"
                    data-phase={phase}
                    data-backend={backendStatus}
                    data-no-audio={noAudio}
                  >
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: phaseColor(phase, backendStatus, noAudio) }}
                    />
                    {phaseLabel(phase, backendStatus, noAudio)}
                  </div>
                </div>

                {/* ── 음성인식 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base">음성인식</p>
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={() => void onStart()}
                      variant="outline"
                      disabled={!canStart || isPaused || isStopping}
                      data-testid="stt-start"
                    >
                      시작
                    </Button>
                    {/* 일시중단 상태에서 '재개'는 새 WS 세션을 연다 —
                        서버는 1연결=1세션이라 기존 연결로는 다시 전사할 수 없다. */}
                    <Button
                      onClick={isPaused || isStopping ? () => void onStart() : onPause}
                      variant="outline"
                      disabled={!canPauseOrResume || busy}
                      data-testid="stt-pause"
                      data-action={isPaused || isStopping ? 'resume' : 'pause'}
                    >
                      {isPaused || isStopping ? '재개' : '일시 중단'}
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        {/* 경로 C 하니스는 이 버튼을 절대 누르지 않는다 —
                            onStop(endSession('stop'))이 화면 전사를 즉시 비워 스크래핑 대상이 사라진다. */}
                        <Button variant="outline" disabled={!canStop || busy} data-testid="stt-stop">
                          종료
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>음성인식종료</AlertDialogTitle>
                          <AlertDialogDescription>
                            종료를 진행할 경우 번역 기록이 초기화됩니다.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>취소</AlertDialogCancel>
                          <AlertDialogAction onClick={onStop}>확인</AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>

                {/* ── 웨이브폼 ── */}
                {(phase === 'recording' || isPaused) && (
                  <WaveformVisualizer analyserNode={analyser} isActive={phase === 'recording'} />
                )}

                {/* ── 언어 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base flex-grow-0">언어</p>
                  <select
                    value={language}
                    disabled={!canChangeLanguage}
                    onChange={(e) => setLanguage(e.target.value as SourceLanguage)}
                    className={SELECT_CLASS}
                    data-testid="stt-language"
                    title={canChangeLanguage ? undefined : '언어는 시작 전에만 변경할 수 있습니다'}
                  >
                    {LANGUAGE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* ── 시각 표시 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base flex-grow-0">시각 표시</p>
                  <select
                    value={showTimestamp ? 'on' : 'off'}
                    onChange={(e) => setShowTimestamp(e.target.value === 'on')}
                    className={SELECT_CLASS}
                  >
                    <option value="off">숨김</option>
                    <option value="on">표시</option>
                  </select>
                </div>

                {/* ── 원본 폰트 크기 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base flex-grow-0">원본 폰트 크기</p>
                  <Input
                    className="w-min"
                    type="number"
                    min="12"
                    max="60"
                    value={fontSizeOriginal}
                    onChange={(e) => setFontSizeOriginal(parseInt(e.target.value) || 0)}
                  />
                </div>

                {/* ── 번역 폰트 크기 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base flex-grow-0">번역 폰트 크기</p>
                  <Input
                    className="w-min"
                    type="number"
                    min="12"
                    max="48"
                    value={fontSizeTranslation}
                    onChange={(e) => setFontSizeTranslation(parseInt(e.target.value) || 0)}
                  />
                </div>

                {/* ── 시스템 폰트 크기 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base flex-grow-0">시스템 폰트 크기</p>
                  <Input
                    className="w-min"
                    type="number"
                    min="10"
                    max="36"
                    value={fontSizeSystem}
                    onChange={(e) => setFontSizeSystem(parseInt(e.target.value) || 0)}
                  />
                </div>

                {/* ── 원본 폰트 색상 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base flex-grow-0">원본 폰트 색상</p>
                  <Input
                    className="w-12"
                    type="color"
                    value={colorOriginalForeground}
                    onChange={(e) => setColorOriginalForeground(e.target.value)}
                  />
                </div>

                {/* ── 번역 폰트 색상 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base flex-grow-0">번역 폰트 색상</p>
                  <Input
                    className="w-12"
                    type="color"
                    value={colorTranslationForeground}
                    onChange={(e) => setColorTranslationForeground(e.target.value)}
                  />
                </div>

                {/* ── 시스템 폰트 색상 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base flex-grow-0">시스템 폰트 색상</p>
                  <Input
                    className="w-12"
                    type="color"
                    value={colorSystemForeground}
                    onChange={(e) => setColorSystemForeground(e.target.value)}
                  />
                </div>

                {/* ── 배경 색상 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base flex-grow-0">배경 색상</p>
                  <Input
                    className="w-12"
                    type="color"
                    value={backgroundColor}
                    onChange={(e) => setBackgroundColor(e.target.value)}
                  />
                </div>

                {/* ── 로고 배경 색상 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base flex-grow-0">로고 배경 색상</p>
                  <Input
                    className="w-12"
                    type="color"
                    value={titleBackgroundColor}
                    onChange={(e) => setTitleBackgroundColor(e.target.value)}
                  />
                </div>

                {/* ── 로고 폰트 색상 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base flex-grow-0">로고 폰트 색상</p>
                  <Input
                    className="w-12"
                    type="color"
                    value={colorTitleForeground}
                    onChange={(e) => setColorTitleForeground(e.target.value)}
                  />
                </div>

                {/* ── 로고 전체 크기 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base flex-grow-0">로고 전체 크기</p>
                  <select
                    value={logoSize}
                    onChange={(e) => setLogoSize(e.target.value as 'sm' | 'md' | 'lg' | 'xl')}
                    className={SELECT_CLASS}
                  >
                    <option value="sm">50%</option>
                    <option value="md">100%</option>
                    <option value="lg">150%</option>
                    <option value="xl">200%</option>
                  </select>
                </div>

                {/* ── 초기화 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base">초기화</p>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" onClick={onReset} disabled={phase === 'recording'}>
                      기록 초기화
                    </Button>
                    <Button variant="outline" onClick={handleResetTheme}>
                      설정 초기화
                    </Button>
                  </div>
                </div>

                {/* ── 관리자 페이지 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base">관리자 페이지</p>
                  <div className="flex items-center gap-2">
                    <a href={`${BASE_PATH}/admin`} target="_blank" rel="noopener noreferrer">
                      <Button variant="outline">이동</Button>
                    </a>
                  </div>
                </div>

                {/* ── Footer: 저작권 / 보안고지 ── */}
                <div className="flex-shrink-0 border-t pt-3 mt-2">
                  <p className="text-xs text-muted-foreground">
                    Copyright &copy; 2026 Republic of Korea Air Force.
                    <br />
                    All Right Reserved v.{APP_VERSION || '1.0.0'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-2">
                    본 프로그램의 대외유출을 금하며, 본 프로그램을 활용하여 생산한 자료는
                    군사기밀보호법 및 국방보안업무훈령을 준수하여 운영 바랍니다.
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};

function phaseLabel(phase: string, backend: string, noAudio: boolean): string {
  if (backend === 'unhealthy') return '서버 연결 불가';
  switch (phase) {
    case 'connecting':
      return '연결 중';
    case 'recording':
      return noAudio ? '입력 음성 없음' : '인식 중';
    case 'stopping':
      return '마무리 중';
    case 'paused':
      return '일시 중단';
    case 'error':
      return '오류';
    default:
      return '대기';
  }
}

function phaseColor(phase: string, backend: string, noAudio: boolean): string {
  if (backend === 'unhealthy' || phase === 'error') return '#ef4444';
  // 무음은 오류가 아니라 주의 — 연결 중과 같은 노란색을 쓴다(새 색을 도입하지 않는다).
  if (phase === 'recording') return noAudio ? '#eab308' : '#22c55e';
  if (phase === 'connecting' || phase === 'stopping') return '#eab308';
  return '#6b7280';
}

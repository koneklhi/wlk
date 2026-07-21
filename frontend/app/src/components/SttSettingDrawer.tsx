/**
 * @fileoverview STT 설정 panel — 오른쪽 slide-in drawer (stt-frontend 평면 스타일)
 *
 * UI 형태는 기존 배포 UI 그대로 유지한다. 바뀐 것은 두 가지뿐:
 *   ① 버튼 활성/비활성을 세션 phase 에서 파생 — 예전에는 자체 boolean 을 봐서 종료 후 먹통이 됐다.
 *   ② 언어 select 가 즉시 재연결하지 않고 값만 저장 — 세션 중 언어 변경은 새 연결이 필요하다.
 * 그리고 기존 행 스타일 그대로 '전사 저장'·'시각 표시' 두 행을 추가했다.
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
import { saveTranscript } from '@/api/transcript';
import { useTranscriptRows } from '@/hooks/useTranscriptRows';
import useSettingSidebarStore from '@/stores/stt-sidebar-store';
import { useSttStore } from '@/stores/stt.store';
import { useThemeStore } from '@/stores/theme.store';
import { LANGUAGE_OPTIONS, type SourceLanguage } from '@/types/stt';
import { toSavePayload } from '@/utils/transcriptRows';
import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';
import { useCallback, useState } from 'react';
import { toast } from 'react-toastify';

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
  const [saving, setSaving] = useState(false);

  // 세션이 살아있는 동안(connecting/stopping)에는 소켓 재생성이 필요한 조작을 막는다.
  const busy = phase === 'connecting' || phase === 'stopping';
  const isPaused = phase === 'paused';
  const canStart = !busy && (phase === 'idle' || isPaused || phase === 'error');
  const canPauseOrResume = phase === 'recording' || isPaused;
  const canStop = phase === 'recording' || isPaused;
  const canChangeLanguage = phase === 'idle' || phase === 'error';
  const hasTranscript = rows.length > 0;

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

  const handleSave = useCallback(async () => {
    const lines = toSavePayload(rows);
    if (lines.length === 0) {
      toast.warn('저장할 전사 내용이 없습니다.');
      return;
    }
    setSaving(true);
    try {
      const res = await saveTranscript({ lines });
      toast.success(`전사 ${res.line_count}줄을 저장했습니다.`);
    } catch (e) {
      toast.error(`저장 실패: ${e instanceof Error ? e.message : '알 수 없는 오류'}`);
    } finally {
      setSaving(false);
    }
  }, [rows]);

  return (
    <>
      {/* sidebar toggle button */}
      {!isOpenSidebar && (
        <div className="fixed h-full right-0 flex items-center pr-2 z-[150]">
          <Button size="icon" variant="ghost" onClick={toggleSidebar}>
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
                  <div className="flex items-center gap-1.5 text-sm font-mono">
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: phaseColor(phase, backendStatus) }}
                    />
                    {phaseLabel(phase, backendStatus)}
                  </div>
                </div>

                {/* ── 음성인식 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base">음성인식</p>
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={() => void onStart()}
                      variant="outline"
                      disabled={!canStart || isPaused}
                    >
                      시작
                    </Button>
                    {/* 일시중단 상태에서 '재개'는 새 WS 세션을 연다 —
                        서버는 1연결=1세션이라 기존 연결로는 다시 전사할 수 없다. */}
                    <Button
                      onClick={isPaused ? () => void onStart() : onPause}
                      variant="outline"
                      disabled={!canPauseOrResume || busy}
                    >
                      {isPaused ? '재개' : '일시 중단'}
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="outline" disabled={!canStop || busy}>
                          종료
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>녹음 종료</AlertDialogTitle>
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
                    title={canChangeLanguage ? undefined : '언어는 시작 전에만 변경할 수 있습니다'}
                  >
                    {LANGUAGE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* ── 전사 저장 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base">전사 저장</p>
                  <Button
                    variant="outline"
                    onClick={() => void handleSave()}
                    disabled={saving || !hasTranscript}
                  >
                    {saving ? '저장 중...' : '저장'}
                  </Button>
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

function phaseLabel(phase: string, backend: string): string {
  if (backend === 'unhealthy') return '서버 연결 불가';
  switch (phase) {
    case 'connecting':
      return '연결 중';
    case 'recording':
      return '인식 중';
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

function phaseColor(phase: string, backend: string): string {
  if (backend === 'unhealthy' || phase === 'error') return '#ef4444';
  if (phase === 'recording') return '#22c55e';
  if (phase === 'connecting' || phase === 'stopping') return '#eab308';
  return '#6b7280';
}

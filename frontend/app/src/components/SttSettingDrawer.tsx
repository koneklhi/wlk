/**
 * @fileoverview STT 설정 panel — 오른쪽 slide-in drawer (stt-frontend 평면 스타일)
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
import { Server } from '@/constants';
import useSettingSidebarStore from '@/stores/stt-sidebar-store';
import { useSTTStore } from '@/stores/stt.store';
import { useThemeStore } from '@/stores/theme.store';
import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';
import { useCallback } from 'react';

export const SttSettingDrawer = ({
  recordFlow,
  analyser,
  startRecording,
  onPauseRecording,
  onResumeRecording,
  onStopRecording,
  onReset,
}: {
  recordFlow: 'idle' | 'recording' | 'paused' | 'stopping';
  analyser: AnalyserNode | null;
  startRecording: () => Promise<void>;
  onPauseRecording: () => void;
  onResumeRecording: () => void;
  onStopRecording: () => void;
  onReset: () => void;
}) => {
  const { isOpenSidebar, toggleSidebar } = useSettingSidebarStore();
  const connectionStatus = useSTTStore((s) => s.connectionStatus);
  const connect = useSTTStore((s) => s.connect);
  const init = useSTTStore((s) => s.init);

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
  } = useThemeStore();

  const handleResetTheme = useCallback(() => {
    useThemeStore.getState().reset();
  }, []);

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
                      style={{
                        backgroundColor:
                          connectionStatus === 'connected'
                            ? '#22c55e'
                            : connectionStatus === 'connecting'
                            ? '#eab308'
                            : '#ef4444',
                      }}
                    />
                    {connectionStatus === 'connected'
                      ? '연결됨'
                      : connectionStatus === 'connecting'
                      ? '연결 중'
                      : '연결 안됨'}
                  </div>
                </div>

                {/* ── 음성인식 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base">음성인식</p>
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={startRecording}
                      variant="outline"
                      disabled={recordFlow !== 'idle'}
                    >
                      시작
                    </Button>
                    <Button
                      onClick={recordFlow === 'paused' ? onResumeRecording : onPauseRecording}
                      variant="outline"
                      disabled={recordFlow === 'idle' || recordFlow === 'stopping'}
                    >
                      {recordFlow === 'paused' ? '재개' : '일시 중단'}
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="outline"
                          disabled={recordFlow === 'idle' || recordFlow === 'stopping'}
                        >
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
                          <AlertDialogAction onClick={onStopRecording}>
                            확인
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>

                {/* ── 웨이브폼 ── */}
                {(recordFlow === 'recording' || recordFlow === 'paused') && (
                  <WaveformVisualizer
                    analyserNode={analyser}
                    isActive={recordFlow === 'recording'}
                  />
                )}

                {/* ── 언어 ── */}
                <div className="flex justify-between items-center">
                  <p className="font-semibold text-base flex-grow-0">언어</p>
                  <select
                    defaultValue="AUTO"
                    onChange={(e) => connect(Server.WS_URL, e.target.value as 'KOR' | 'ENG' | 'AUTO')}
                    className="h-10 px-3 text-sm bg-background border border-input rounded-md text-foreground outline-none w-[120px]"
                  >
                    <option value="AUTO">AUTO</option>
                    <option value="KOR">KOR</option>
                    <option value="ENG">ENG</option>
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
                    className="h-10 px-3 text-sm bg-background border border-input rounded-md text-foreground outline-none w-[120px]"
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
                    <Button variant="outline" onClick={onReset}>
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
                    <a href={`${import.meta.env.VITE_BASE_URL ?? '/wlkies'}/admin`} target="_blank" rel="noopener noreferrer">
                      <Button variant="outline">이동</Button>
                    </a>
                  </div>
                </div>

                {/* ── Footer: 저작권 / 보안고지 ── */}
                <div className="flex-shrink-0 border-t pt-3 mt-2">
                  <p className="text-xs text-muted-foreground">
                    Copyright &copy; 2026 Republic of Korea Air Force.
                    <br />
                    All Right Reserved v.{import.meta.env.VITE_APP_VERSION ?? '1.0.0'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-2">
                    본 프로그램의 대외유출을 금하며, 본 프로그램을 활용하여 생산한 자료는 군사기밀보호법 및 국방보안업무훈령을 준수하여
                    운영 바랍니다.
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

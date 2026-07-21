/**
 * @fileoverview 백엔드 도달 불가 안내 오버레이. (UI 는 기존 그대로)
 *
 * 예전에는 `lastHttpStatus === 500` 일 때만 떠서 사실상 죽은 코드였다 —
 * 헬스 경로가 틀려(/wlkies/health) SPA fallback 이 HTML 을 돌려줬고, 그러면 status 가 잡히지
 * 않아 조건이 영원히 거짓이었다. 지금은 헬스 실패 자체를 조건으로 쓴다.
 */
import { ArrowUpFromLine, RotateCw, WifiOff } from 'lucide-react';

export function BackendErrorOverlay({
  isConnecting,
  onClose,
  status,
}: {
  isConnecting: boolean;
  onClose?: () => void;
  status?: number | null;
}) {
  const isServerError = status === 500;

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-[#050608]/60 backdrop-blur-sm font-mono">
      <div className="text-center max-w-sm px-6">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 border border-red-500/20 mb-4">
          {isConnecting ? (
            <RotateCw size={28} className="text-red-400 animate-spin" />
          ) : (
            <WifiOff size={28} className="text-red-400" />
          )}
        </div>

        <h2 className="text-lg font-bold text-red-400 mb-1 uppercase tracking-widest">
          {isConnecting ? '연결 시도 중...' : isServerError ? '시스템 통신 오류' : '네트워크 연결 불가'}
        </h2>
        <p className="text-sm text-white/40 mb-4 leading-relaxed">
          {isConnecting
            ? '백엔드 서버의 응답을 대기하고 있습니다.'
            : isServerError
            ? '백엔드 서버 내부 처리 오류(500)가 발생했습니다. 관리자에게 보고하십시오.'
            : '서버 실행 상태 및 방화벽 설정을 확인하십시오.'}
        </p>

        {onClose && !isConnecting && (
          <button
            onClick={onClose}
            className="inline-flex items-center gap-1.5 h-8 px-4 rounded-none text-xs font-bold border border-red-500/50 text-red-400 hover:bg-red-500/10 transition-colors uppercase tracking-widest"
          >
            <ArrowUpFromLine size={12} />
            재연결 시도
          </button>
        )}
      </div>
    </div>
  );
}

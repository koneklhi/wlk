/**
 * @fileoverview 관리자 페이지 — 단어교정 · 번역용어 · 번역예시를 한 화면에 (HUD 스타일).
 *
 * 탭 없이 좌우 2분할이다: 좌 = 단어교정, 우 = 번역용어(위) + 번역예시(아래).
 * 세 목록 모두 **사용자가 관리자 페이지에서 직접 넣은 DB 항목만** 보인다 —
 * 배포 전 관리자가 미리 채우는 정적 JSON 기본값은 서버가 응답에서 제외한다
 * (`GET /api/corrections`, `GET /api/prompts` glossary_block. 정본 = docs/API_SPEC.md §3.3·§3.4).
 * 숨겨진 기본값도 전사·번역에는 그대로 적용된다.
 */
import { createFileRoute } from '@tanstack/react-router';
import { BookOpen, Loader2, Languages, MessageSquare, Plus, Trash2, ArrowRight, type LucideIcon } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { toast } from 'react-toastify';
import {
  addCorrection,
  addPromptItem,
  deleteCorrection,
  deletePromptItem,
  getCorrections,
  getPrompts,
} from '@/api/corrections';
import { BlockControlPanel } from '@/components/BlockControlPanel';
import { Input } from '@/components/ui/input';
import { cn } from '@/utils';

/* ═══════ Route ═══════ */

export const Route = createFileRoute('/admin')({
  component: AdminPage,
});

/* ═══════ Types ═══════ */

/** 실제 데이터 소스 종류. useItems/SectionUI/AddDialog 가 받는 값. */
type ItemKind = 'words' | 'translate_words' | 'translate_sentence';

/* ═══════ Labels per section ═══════ */

const SECTION_LABELS: Record<ItemKind, { title: string; addBtn: string; srcLabel: string; dstLabel: string }> = {
  words: { title: '단어교정', addBtn: '단어 추가', srcLabel: '오인식 단어', dstLabel: '목표 단어' },
  translate_words: { title: '번역용어', addBtn: '용어 추가', srcLabel: '원본 단어', dstLabel: '번역 단어' },
  translate_sentence: { title: '번역예시', addBtn: '예시 추가', srcLabel: '원본 문장', dstLabel: '번역 문장' },
};

/* ═══════ Hooks ═══════ */

interface ItemEntry {
  src: string;
  dst: string;
}

/** 번역 사전은 두 블록으로 나뉜다. 단어교정('words')은 별도 API 라 여기 해당 없음. */
const BLOCK_KEY = {
  translate_words: 'glossary_block',
  translate_sentence: 'sentence_block',
} as const;

function useItems(type: ItemKind) {
  const [items, setItems] = useState<ItemEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notSupported, setNotSupported] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);

    if (type === 'words') {
      getCorrections()
        .then((data) => setItems(Object.entries(data).map(([src, dst]) => ({ src, dst }))))
        .catch(() => setError('단어교정 목록을 불러오지 못했습니다.'))
        .finally(() => setLoading(false));
    } else {
      const blockKey = BLOCK_KEY[type];
      getPrompts()
        .then((data) => {
          const block = data[blockKey] as Record<string, string> | undefined;
          setItems(
            block && typeof block === 'object'
              ? Object.entries(block).map(([src, dst]) => ({ src, dst }))
              : [],
          );
          setNotSupported(false);
        })
        .catch((e) => {
          if ((e as Error & { status?: number }).status === 404) {
            setNotSupported(true);
            setItems([]);
          } else {
            setError('번역 교정 목록을 불러오지 못했습니다.');
          }
        })
        .finally(() => setLoading(false));
    }
  }, [type]);

  useEffect(() => { load(); }, [load]);

  const addItem = useCallback(async (src: string, dst: string) => {
    setError(null);
    try {
      if (type === 'words') {
        await addCorrection(src, dst);
      } else {
        await addPromptItem(BLOCK_KEY[type], src, dst);
      }
      toast.success(`[${src} → ${dst}] 등록 성공`);
      load();
    } catch (e) {
      toast.error(`${SECTION_LABELS[type].title} 추가 중 문제가 발생했습니다.`);
      // 재던진다 — 등록 창이 열린 채로 유지되므로 호출측(AddDialog)이 성공/실패를 구분해
      // 실패했을 때 입력값을 지우지 않아야 한다.
      throw e;
    }
  }, [type, load]);

  const removeItem = useCallback(async (src: string) => {
    setError(null);
    try {
      if (type === 'words') {
        // 기본 단어교정 사전 항목은 삭제할 수 없다 — 서버가 HTTP 200 + status:'warning' 으로 알려준다.
        const res = await deleteCorrection(src);
        if (res.status === 'warning') {
          toast.warn(res.message ?? '삭제할 수 없는 항목입니다.');
          return;
        }
      } else {
        // 기본 glossary 항목은 삭제할 수 없다 — 서버가 HTTP 200 + status:'warning' 으로 알려준다.
        const res = await deletePromptItem(BLOCK_KEY[type], src);
        if (res.status === 'warning') {
          toast.warn(res.message ?? '삭제할 수 없는 항목입니다.');
          return;
        }
      }
      toast.success(`[${src}] 삭제 성공`);
      load();
    } catch {
      toast.error('삭제 중 문제가 발생했습니다.');
    }
  }, [type, load]);

  return { items, loading, error, notSupported, addItem, removeItem };
}

/* ═══════ Add Dialog ═══════ */

/**
 * 등록 창. **연속 입력**을 전제로 만든다 — 열면 첫 칸(`srcLabel`)에 커서가 잡히고,
 * 등록해도 창이 닫히지 않고 두 칸만 비워진 뒤 커서가 다시 첫 칸으로 돌아온다.
 * 그래서 항목 여러 개를 마우스 없이 이어서 넣을 수 있다.
 * 닫기는 ESC · 취소 · X · 바깥 클릭 네 경로 모두 `close()` 하나를 거친다.
 */
function AddDialog({ open, type, onClose, onConfirm }: {
  open: boolean;
  type: ItemKind;
  onClose: () => void;
  onConfirm: (src: string, dst: string) => Promise<void>;
}) {
  const [src, setSrc] = useState('');
  const [dst, setDst] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const srcRef = useRef<HTMLInputElement>(null);
  const labels = SECTION_LABELS[type];

  /** 닫기 경로 공용 — 다음에 열 때 항상 빈 칸이도록 정리하고 닫는다. */
  const close = useCallback(() => {
    setSrc('');
    setDst('');
    setError(null);
    onClose();
  }, [onClose]);

  const handleSubmit = async () => {
    if (saving || !src.trim() || !dst.trim()) return;  // Enter 연타·더블클릭 가드
    setError(null);
    setSaving(true);
    try {
      await onConfirm(src.trim(), dst.trim());
      // 창은 그대로 두고 곧바로 다음 항목을 칠 수 있게 한다.
      setSrc('');
      setDst('');
      srcRef.current?.focus();  // 마우스로 '등록'을 눌렀다면 포커스가 버튼에 가 있다
    } catch {
      /* 실패 안내는 onConfirm(useItems.addItem)이 toast 로 띄운다. 입력값은 지우지 않는다. */
      setError('추가하지 못했습니다.');
    } finally {
      setSaving(false);
    }
  };

  /** Enter = 등록. 한글 조합 중(IME 미확정)의 Enter 는 조합을 끝내는 키라 흘려보낸다. */
  const handleKeyDown = (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter' || e.nativeEvent.isComposing) return;
    e.preventDefault();
    void handleSubmit();
  };

  // 열릴 때마다 첫 칸에 커서를 잡아준다(닫혀 있으면 DOM 자체가 없으므로 열리는 렌더의 커밋 직후 실행).
  useEffect(() => {
    if (open) srcRef.current?.focus();
  }, [open]);

  // ESC 로 닫기. 포커스가 입력칸·버튼 어디에 있든 받아야 해서 window 에 건다.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !e.isComposing) close();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, close]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={close}
    >
      <div
        className="bg-[#141414] border border-white/[0.08] w-[400px]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
          <span className="text-sm font-bold tracking-wide uppercase text-white/70">{labels.title} — 등록</span>
          <button onClick={close} className="w-6 h-6 flex items-center justify-center hover:bg-white/5 text-white/30 hover:text-white/60 transition-colors">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </div>

        <div className="p-6 space-y-3">
          <div>
            <label className="text-xs text-white/40 mb-1 block">{labels.srcLabel}</label>
            <Input
              ref={srcRef}
              value={src}
              onChange={(e) => setSrc(e.target.value)}
              onKeyDown={handleKeyDown}
              className="bg-[#080808] border-white/[0.06] text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-white/40 mb-1 block">{labels.dstLabel}</label>
            <Input
              value={dst}
              onChange={(e) => setDst(e.target.value)}
              onKeyDown={handleKeyDown}
              className="bg-[#080808] border-white/[0.06] text-sm"
            />
          </div>
          {error && <p className="text-red-400 text-xs">{error}</p>}
        </div>

        <div className="flex justify-end gap-2 px-5 py-3 border-t border-white/[0.06]">
          <button
            onClick={close}
            className="h-8 px-4 text-sm border border-white/10 text-white/50 hover:bg-white/5 transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving || !src.trim() || !dst.trim()}
            className="h-8 px-4 text-sm bg-blue-500/20 border border-blue-500/30 text-blue-400 hover:bg-blue-500/30 disabled:opacity-40 transition-colors"
          >
            {saving ? '저장 중...' : '등록'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ═══════ Item Card ═══════ */

function ItemCard({ src, dst, onRemove }: { src: string; dst: string; onRemove: () => void }) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 border border-white/[0.04] hover:border-white/[0.08] transition-colors rounded-lg">
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <span className="text-base text-white/60 truncate">{src}</span>
        <ArrowRight size={16} className="text-white/20 shrink-0" />
        <span className="text-base text-white/90 truncate">{dst}</span>
      </div>
      <button
        onClick={onRemove}
        className="shrink-0 w-8 h-8 flex items-center justify-center text-white/15 hover:text-red-400 hover:bg-red-500/10 transition-colors rounded"
        title="삭제"
      >
        <Trash2 size={16} />
      </button>
    </div>
  );
}

/* ═══════ Section UI (pure rendering) ═══════ */

function SectionUI({
  type, Icon, labels, className,
  items, loading, error, notSupported,
  search, setSearch, addOpen, setAddOpen,
  addItem, removeItem,
}: {
  type: ItemKind;
  Icon?: LucideIcon;
  labels: { title: string; addBtn: string; srcLabel: string; dstLabel: string };
  className?: string;
  items: ItemEntry[];
  loading: boolean;
  error: string | null;
  notSupported: boolean;
  search: string;
  setSearch: (v: string) => void;
  addOpen: boolean;
  setAddOpen: (v: boolean) => void;
  addItem: (s: string, d: string) => Promise<void>;
  removeItem: (s: string) => Promise<void>;
}) {
  const filtered = useMemo(() =>
    items.filter(
      (item) =>
        item.src.toLowerCase().includes(search.toLowerCase()) ||
        item.dst.toLowerCase().includes(search.toLowerCase()),
    ),
    [items, search],
  );

  // AddDialog 의 ESC 리스너 의존성이라 안정적이어야 한다 — 인라인 함수면 타이핑 한 글자마다 재구독된다.
  const closeAdd = useCallback(() => setAddOpen(false), [setAddOpen]);

  if (notSupported) {
    return (
      <div className={cn(className, "rounded border border-dashed border-white/[0.06] p-10 text-center")}>
        <p className="text-sm text-white/30">번역 교정 API가 연결되지 않았습니다</p>
        <p className="text-xs text-white/15 mt-1">백엔드 /prompts API 확인 필요</p>
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {Icon && <Icon size={18} className="text-white/30" />}
          <h3 className="text-base font-bold text-white/80 uppercase tracking-wider">{labels.title} <span className="text-base text-white/25 font-normal">({items.length})</span></h3>
        </div>
        <button
          onClick={() => setAddOpen(true)}
          className="h-9 px-4 text-sm border border-white/10 text-white/50 hover:bg-white/5 hover:text-white/70 flex items-center gap-1.5 transition-colors"
        >
          <Plus size={12} />
          {labels.addBtn}
        </button>
      </div>

      <Input
        placeholder="검색..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="bg-[#080808] border-white/[0.06] text-sm h-9"
      />

      {loading ? (
        <div className="flex items-center justify-center py-10">
          <Loader2 className="w-6 h-6 animate-spin text-white/20" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex items-center justify-center py-10">
          <p className="text-sm text-white/25">{search ? '검색된 결과가 없습니다' : '등록된 항목이 없습니다'}</p>
        </div>
      ) : (
        <div className="space-y-2 flex-1 min-h-0 overflow-y-auto pr-1">
          {filtered.map((item) => (
            // key 는 원본 단어(dict 키라 목록 내 유일). 배열 index 를 쓰면 삭제·필터 시
            // 남은 항목이 앞 항목의 DOM 을 재사용해 엉뚱한 행이 지워진 것처럼 보인다.
            <ItemCard key={item.src} src={item.src} dst={item.dst} onRemove={() => removeItem(item.src)} />
          ))}
        </div>
      )}

      {error && <p className="text-xs text-red-400">{error}</p>}

      <AddDialog open={addOpen} type={type} onClose={closeAdd} onConfirm={addItem} />
    </div>
  );
}

/* ═══════ Section (데이터 소스 1개 = 패널 1개) ═══════ */

/**
 * `useItems` + 검색어 + 추가 다이얼로그 상태를 자기 안에 들고 `SectionUI` 에 넘기는 래퍼.
 * 배치(폭·높이)는 `className` 으로 부모가 정한다 — 세 패널이 같은 컴포넌트를 쓴다.
 */
function Section({ type, Icon, className }: { type: ItemKind; Icon: LucideIcon; className?: string }) {
  const { items, loading, error, notSupported, addItem, removeItem } = useItems(type);
  const [search, setSearch] = useState('');
  const [addOpen, setAddOpen] = useState(false);

  return (
    <SectionUI
      type={type} Icon={Icon} labels={SECTION_LABELS[type]} className={className}
      items={items} loading={loading} error={error} notSupported={notSupported}
      search={search} setSearch={setSearch} addOpen={addOpen} setAddOpen={setAddOpen}
      addItem={addItem} removeItem={removeItem}
    />
  );
}

/* ═══════ Admin Page ═══════ */

/**
 * 한 페이지에 세 사전을 모두 펼친다 — 탭 없음.
 * 좌: 블록 관리(위) + 단어교정(아래) / 우: 번역용어(위) + 번역예시(아래).
 *
 * 블록 관리만 성격이 다르다 — 사전이 아니라 **실시간 화면 조작**이라 서버가 아닌 다른 창에
 * 명령을 보낸다(BlockControlPanel 참조). 높이는 내용만큼만 쓰도록 shrink-0 으로 둔다.
 *
 * 페이지 전체 스크롤이 아니라 **패널별 내부 스크롤**이다(`SectionUI` 의 목록 div 가
 * `flex-1 min-h-0 overflow-y-auto`). 그래서 바깥 컨테이너는 높이를 고정해 주고
 * (`flex-1 min-h-0`), 각 패널에도 `min-h-0` 를 내려 flex 자식이 넘치지 않게 한다.
 */
function AdminPage() {
  return (
    <div className="w-screen h-screen flex flex-col bg-[#0a0b0c] text-white overflow-hidden">
      {/* Header */}
      <div className="shrink-0 relative flex items-center gap-4 px-6 py-3 bg-[#0D0F12] border-b border-white/10">
        {/* Corner brackets */}
        <div className="absolute left-0 top-0 w-3 h-3 border-l border-t border-white/20" />
        <div className="absolute right-0 top-0 w-3 h-3 border-r border-t border-white/20" />

        <h1 className="text-sm font-bold tracking-[0.15em] uppercase text-white/60 font-mono">관리자</h1>
      </div>

      {/* Content — 좌: 단어교정 / 우: 번역용어 + 번역예시 */}
      <div className="flex-1 min-h-0 flex flex-row gap-6 px-8 py-6">
        <div className="flex-1 min-w-0 flex flex-col gap-6">
          <BlockControlPanel className="shrink-0" />
          <div className="h-px shrink-0 bg-white/[0.06]" />
          <Section type="words" Icon={BookOpen} className="flex-1 min-h-0" />
        </div>

        <div className="w-px shrink-0 bg-white/[0.06]" />

        <div className="flex-1 min-w-0 flex flex-col gap-6">
          <Section type="translate_words" Icon={Languages} className="flex-1 min-h-0" />
          <div className="h-px shrink-0 bg-white/[0.06]" />
          <Section type="translate_sentence" Icon={MessageSquare} className="flex-1 min-h-0" />
        </div>
      </div>
    </div>
  );
}

export { AdminPage };

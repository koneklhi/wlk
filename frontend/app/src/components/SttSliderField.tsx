/**
 * @fileoverview 설정 드로어용 수치 입력 행 — 슬라이더 + 숫자 입력 겸용
 *
 * 드로어의 기존 행 레이아웃(`flex justify-between items-center` + `font-semibold text-base` 라벨)을
 * 그대로 따르되, 오른쪽에 range 와 number 를 나란히 둔다. 둘은 같은 store 값을 보고 쓴다.
 *
 * range 는 네이티브 `<input type="range">` 다 — 폐쇄망 패키징에 새 npm 의존성(radix slider)을
 * 얹지 않기 위해서다. 겉모습은 styles.css 의 `.stt-range` 가 맞춘다.
 */
import { Input } from '@/components/ui/input';
import { useState } from 'react';

interface SttSliderFieldProps {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  /** 숫자 뒤에 붙일 단위 표기(%, px, 배). 없으면 표기하지 않는다. */
  suffix?: string;
}

export const SttSliderField = ({
  label,
  value,
  onChange,
  min,
  max,
  step,
  suffix,
}: SttSliderFieldProps) => {
  // 숫자 칸은 타이핑 중간 상태("", "0.", "-")를 그대로 보여줘야 해서 문자열 draft 를 따로 둔다.
  // store 값이 밖에서 바뀌면(슬라이더 조작·설정 초기화) draft 를 다시 맞춘다 —
  // effect 가 아니라 '이전 값 저장 state 를 render 중 조건부 갱신'하는 React 표준 패턴을 쓴다
  // (effect 안 setState 는 연쇄 렌더를 유발해 lint 가 막는다. SttTextViewer 도 같은 패턴).
  const [draft, setDraft] = useState(String(value));
  const [lastValue, setLastValue] = useState(value);
  if (value !== lastValue) {
    setLastValue(value);
    setDraft(String(value));
  }

  const commit = (raw: string) => {
    setDraft(raw);
    const parsed = parseFloat(raw);
    // 파싱이 안 되는 중간 상태는 store 에 넣지 않는다 — 넣으면 NaN 이 CSS 변수로 새어나간다.
    if (Number.isFinite(parsed)) onChange(clamp(parsed, min, max));
  };

  return (
    <div className="flex justify-between items-center gap-3">
      <p className="font-semibold text-base flex-grow-0 shrink-0">{label}</p>
      <div className="flex items-center gap-2 flex-1 justify-end">
        <input
          type="range"
          className="stt-range flex-1 min-w-0"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(clamp(parseFloat(e.target.value), min, max))}
          aria-label={label}
        />
        <Input
          className="w-[68px] shrink-0 px-2"
          type="number"
          min={min}
          max={max}
          step={step}
          value={draft}
          onChange={(e) => commit(e.target.value)}
          // 빈 문자열·범위 밖 입력이 칸에 남지 않도록 포커스를 잃을 때 store 값으로 되돌린다.
          onBlur={() => setDraft(String(value))}
          aria-label={`${label} 값`}
        />
        {suffix && <span className="text-sm text-muted-foreground w-5 shrink-0">{suffix}</span>}
      </div>
    </div>
  );
};

function clamp(v: number, min: number, max: number): number {
  if (!Number.isFinite(v)) return min;
  return Math.min(max, Math.max(min, v));
}

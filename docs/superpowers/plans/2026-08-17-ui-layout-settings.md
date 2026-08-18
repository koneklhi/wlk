# 배포 UI — 화면 레이아웃 설정 5종 추가

> **상태: 구현 완료 (2026-08-18).** 브랜치 `feat/ui-layout-settings`(워크트리
> `worktrees/ui-layout-settings`), 분기 기준 `master` @ `8af6205`. 구현 1~8 전부 반영했고
> `pnpm lint`(신규 오류 0 — 기존 5건은 master에도 동일하게 있음)·`pnpm build` 통과.
>
> 계획 대비 달라진 점 2가지:
> - `docs/FILE_INDEX.md`는 **갱신하지 않았다** — 이 문서는 프런트 개별 컴포넌트를 색인하지 않고
>   `frontend/app/README.md`로만 연결한다(신규 파일 행을 넣을 자리가 없음). README에는 반영했다.
> - `useSttTextStyle`의 `lineHeight` 하드코딩은 3곳 중 `system` 분기만 들여쓰기가 달라
>   1차 치환에서 누락됐다가 별도로 고쳤다 — 3곳 모두 `var(--stt-line-height)`다.
>
> 남은 것 = 아래 "검증" A(육안, 백엔드+마이크 필요)와 C(선택, 경로 C 스크래핑 계약 회귀).
> B(lint·build)는 완료.

## Context

배포 UI(`frontend/app/`)의 전사 화면은 여백·간격·투명도가 전부 소스에 하드코딩돼 있다
(`px-16`, `gap-14`, `gap-2`, `lineHeight: 1.75`, `opacity: 0.4`, `pb-12`). 배포 현장마다
화면 크기·시청 거리·조명이 달라 운용자가 현장에서 가독성을 맞출 수단이 없다.

특히 화면이 텍스트로 가득 차면 최신 전사가 화면 맨 아래 모서리에 붙어 읽기 불편하다는 문제가
실사용에서 확인됐다.

목표: 설정 드로어에서 아래 5개를 실시간 조절 가능하게 하고, localStorage에 영속화한다.

1. 화면 좌우 여백
2. 문단(블록) 간격 — 블록 = 전사 1문장 + 그 번역
3. 문장 간격 — 줄바꿈 내부 줄간격 + 원문↔번역 간격을 **한 배율**로 동시 조절
4. 번역 중(미확정) 투명도
5. 하단 여백 — 최신 전사가 화면 아래에서 띄워져 보이도록

**STT 파이프라인·서버 계약은 건드리지 않는다.** 순수 프런트 렌더 변경이다.

---

## 확정된 설계 결정 (사용자 확인 완료)

| # | 항목 | 단위 | 기본값 | 범위 (step) |
|---|---|---|---|---|
| 1 | 화면 좌우 여백 | 화면 너비 % (좌우 동일) | `5` | 0–30 (0.5) |
| 2 | 문단 간격 | px 고정값 | `56` | 0–200 (2) |
| 3 | 문장 간격 | 배율 | `1.75` | 1.0–3.0 (0.05) |
| 4 | 번역 중 투명도 | 비율 | `0.4` | 0.1–1.0 (0.05) |
| 5 | 하단 여백 | 화면 높이 % (`vh`) | `20` | 0–60 (1) |

- 컨트롤은 **슬라이더 + 숫자 입력 겸용**(양방향, 같은 store 값)
- 투명도 적용 대상은 **미확정 전사 텍스트 + 번역 대기 로더** 2곳. 시각·확정원인 배지줄(`opacity-50`)은 제외
- 기본값 2·3·4는 현재 화면과 동일. **1(64px→5%)과 5(48px→20vh)만 첫 로드 시 모습이 바뀐다** — 의도된 개선

사용자에게 확인받은 항목(재론 불필요): 문장 간격을 배율 1개로 묶어 줄간격·원문/번역 간격을 동시
조절 / 하단 여백은 설정 항목이며 화면 높이 % / 좌우 여백은 좌우 동일값이며 화면 너비 % /
문단 간격은 px 고정값 / 컨트롤은 슬라이더+숫자 겸용 / 투명도는 미확정 전사 + 번역 대기 로더.

---

## 구현

### 1. `frontend/app/src/stores/theme.store.ts` — store 필드 5개

`STTThemeState` 타입 · `DEFAULTS` · setter 5개를 기존 필드와 같은 형태로 추가한다.

```ts
screenPaddingXPercent: number;   // DEFAULTS: 5
blockGapPx: number;              // DEFAULTS: 56
lineSpacingRatio: number;        // DEFAULTS: 1.75
processingOpacity: number;       // DEFAULTS: 0.4
bottomPaddingPercent: number;    // DEFAULTS: 20
```

**`version`을 올리지 않는다.** `persist`의 기본 merge가 얕은 병합이라, 기존 사용자
localStorage(`stt-theme-v2`)에 이 키들이 없으면 초기 상태의 `DEFAULTS`가 그대로 살아남는다.
`migrate`도 손대지 않는다(기존 저장분은 이미 `version: 1`이라 no-op).

`reset: () => set(() => ({ ...DEFAULTS }))`는 이미 DEFAULTS 전개라 "설정 초기화" 버튼이
신규 항목까지 자동 커버한다 — 별도 작업 없음.

### 2. `frontend/app/src/components/SttThemeProvider.tsx` — CSS 변수 + lineHeight

`cssVars`에 5개 추가:

```ts
['--stt-padding-x']:          `${screenPaddingXPercent}%`,
['--stt-block-gap']:          `${blockGapPx}px`,
['--stt-line-height']:        `${lineSpacingRatio}`,
['--stt-sentence-gap']:       `${(lineSpacingRatio - 1) * fontSizeOriginal * 0.5}px`,
['--stt-processing-opacity']: `${processingOpacity}`,
['--stt-bottom-pad']:         `${bottomPaddingPercent}vh`,
```

**문장 간격 배율 → 두 값 도출 공식**: 배율은 `lineHeight`에 그대로 들어가고, 원문↔번역
간격은 `(배율 − 1) × 원본폰트크기 × 0.5`로 파생시킨다. 기본값 검산 `(1.75−1)×24×0.5 = 9px`
로 현재 `gap-2`(8px)와 사실상 동일해, 배율을 안 건드리면 화면이 그대로다. 배율 1.0에서 간격 0,
3.0에서 24px. `fontSizeOriginal`은 이미 이 컴포넌트가 구독 중이라 추가 구독 불필요.

`useSttTextStyle`의 세 분기 모두 하드코딩 `lineHeight: '1.75'` → `'var(--stt-line-height)'`.

> `--stt-bottom-pad`가 `%`가 아니라 `vh`인 이유: CSS에서 `padding-bottom: N%`는 높이가
> 아니라 **컨테이너 너비** 기준이다. "화면 높이 %"라는 요구를 그대로 구현하려면 `vh`여야 한다.

### 3. `frontend/app/src/components/SttMain.tsx` — 좌우 여백 · 문단 간격 · 하단 spacer

스크롤 컨테이너(`d353a5a` 기준 141–160행)를 이렇게 바꾼다:

```tsx
<div
  ref={scrollBoxRef}
  onScroll={handleScroll}
  className="w-full h-full overflow-y-auto pt-8 custom-scrollbar"   // pb-12 px-16 제거
  style={{
    paddingLeft: 'var(--stt-padding-x)',
    // ⚠️ 아래 '대체' 방식은 최초 설계이며 **폐기됐다**(2026-08-18 수정). 실제 구현은 '합산'이다:
    //   paddingRight: isOpenSidebar ? 'calc(512px + var(--stt-padding-x))' : 'var(--stt-padding-x)'
    // 이유: 슬라이더를 조작하려면 드로어를 열어야 하므로 사용자가 보는 건 항상 이 분기인데,
    // '대체'면 오른쪽이 512px에 고정된 채 왼쪽만 자라 여백이 한쪽에만 먹는 것처럼 보였다.
    // 되돌리지 말 것 — 회귀가 아니라 사용자 확인을 거친 의도된 수정이다.
    paddingRight: isOpenSidebar ? '512px' : 'var(--stt-padding-x)',
  }}
>
  <div className="flex flex-col" style={{ gap: 'var(--stt-block-gap)' }} data-testid="stt-transcript">
    {rows.map(...)}
  </div>
  <div style={{ height: 'var(--stt-bottom-pad)' }} aria-hidden />   {/* 신규 spacer */}
  <div ref={endRef} />                                              {/* sentinel을 spacer 아래로 */}
</div>
```

**하단 여백을 `padding-bottom`으로 하면 안 되는 이유**: 자동 스크롤이
`endRef.scrollIntoView({ block: 'end' })`로 sentinel 바닥을 뷰포트 바닥에 맞춘다. 컨테이너의
padding-bottom은 sentinel **아래**라 화면 밖에 남고, 최신 전사는 여전히 화면 맨 아래에 붙는다.
spacer를 sentinel **위**에 두어야 스크롤이 spacer를 화면 안으로 끌어올려 최신 전사가 위로 밀린다.

sentinel과 spacer는 `stt-transcript` div **바깥**(스크롤 컨테이너 직속)에 둔다. 안에 두면
`--stt-block-gap`이 spacer 앞에 한 번 더 붙는다. 하니스는 `stt-transcript`·`stt-row`만 보므로
sentinel 이동은 측정 계약에 영향 없다(`AUTOSCROLL_THRESHOLD_PX` 로직도 그대로).

### 4. `frontend/app/src/components/SttTextViewer.tsx` — 문장 간격 · 투명도

- 블록 컨테이너(68–74행): `className="flex flex-col gap-2"` → `className="flex flex-col"` +
  `style={{ gap: 'var(--stt-sentence-gap)' }}`.
  이 gap은 [메타줄↔원문]과 [원문↔번역] 둘 다에 걸린다 — 한 블록 내부 간격이 함께 움직이는 것이
  의도(사용자 확인 완료).
- 원문 div(99–105행): `opacity: isProcessing && !hasTranslation ? 0.4 : 1` →
  `? 'var(--stt-processing-opacity)' : 1`. **조건식·`data-testid="stt-text"`·innerText는 불변** —
  경로 C WER 스크래핑에 영향 없다.
- `data-trigger` / `data-finalized` / `data-speaker` / 메타줄이 `stt-text` 바깥에 있는 구조 모두 유지.

### 5. `frontend/app/src/components/SttTranslateLoader.tsx` — 투명도 (래퍼 필요)

현재 `className="... animate-pulse ... opacity-40"`인데, **`animate-pulse` 키프레임이 opacity를
1↔.5로 애니메이션하므로 CSS 애니메이션이 클래스/인라인 opacity를 덮어쓴다** — 즉 지금
`opacity-40`은 이미 무력하다. 설정값이 실제로 먹히게 하려면 투명도를 바깥 래퍼로 올려 곱해지게 한다:

```tsx
<div style={{ opacity: 'var(--stt-processing-opacity)' }}>
  <div className="w-full text-gray-400 text-sm animate-pulse flex gap-1.5 items-center">
    ...기존 내용 그대로...
  </div>
</div>
```

### 6. `frontend/app/src/components/SttSliderField.tsx` — 신규 재사용 컨트롤

드로어의 기존 행 레이아웃(`flex justify-between items-center` + `font-semibold text-base` 라벨)을
따르되, 오른쪽에 `range` + `number`를 나란히 둔다.

```tsx
interface Props { label: string; value: number; onChange: (v: number) => void;
                  min: number; max: number; step: number; suffix?: string; }
```

- `range`는 네이티브 `<input type="range">`. **`@radix-ui/react-slider` 의존성을 추가하지 않는다** —
  폐쇄망 패키징에 새 npm 의존성을 얹지 않기 위해서다(현재 `package.json`에 slider 패키지 없음).
  스타일은 `src/styles.css`에 `.stt-range` 규칙을 기존 `.custom-scrollbar`(88–96행)와 같은 방식으로 추가한다.
- `number`는 기존 `@/components/ui/input`의 `Input` 재사용(`className="w-[68px]"`).
- **입력 처리**: 로컬 draft 문자열 state를 store 값과 동기화하고, `parseFloat`가 유효할 때만
  `min`~`max`로 clamp 해서 store에 커밋한다. `onBlur`에서 store 값으로 재동기화해 빈 문자열·
  범위 밖 입력이 남지 않게 한다. (기존 폰트 크기 행의 `parseInt(...) || 0`은 clamp가 없어
  투명도 같은 소수 값엔 못 쓴다.)
- 드로어 너비 500px 안에서 `[라벨] [range flex-1] [number 68px]`가 한 줄에 들어간다.

### 7. `frontend/app/src/components/SttSettingDrawer.tsx` — 항목 5개 배치

`useThemeStore()` 구조분해에 신규 값·setter 10개 추가. 배치 위치는 **"시스템 폰트 크기"(309–320행)
아래, "원본 폰트 색상"(322–331행) 위** — 크기 그룹과 색상 그룹 사이에 레이아웃 5개를 한 덩어리로.

```tsx
<SttSliderField label="화면 좌우 여백"  value={screenPaddingXPercent} onChange={setScreenPaddingXPercent} min={0}   max={30}  step={0.5}  suffix="%" />
<SttSliderField label="문단 간격"      value={blockGapPx}           onChange={setBlockGapPx}           min={0}   max={200} step={2}    suffix="px" />
<SttSliderField label="문장 간격"      value={lineSpacingRatio}     onChange={setLineSpacingRatio}     min={1}   max={3}   step={0.05} suffix="배" />
<SttSliderField label="번역 중 투명도"  value={processingOpacity}    onChange={setProcessingOpacity}    min={0.1} max={1}   step={0.05} />
<SttSliderField label="하단 여백"      value={bottomPaddingPercent} onChange={setBottomPaddingPercent} min={0}   max={60}  step={1}    suffix="%" />
```

기존 `data-testid`(`stt-settings-toggle`/`stt-start`/`stt-pause`/`stt-stop`/`stt-status`/
`stt-language`)와 `data-phase`는 전혀 손대지 않는다.

### 8. 문서 갱신 (같은 커밋)

- `frontend/app/README.md` — "테마/설정" 절(244–254행)에 신규 5개 항목·단위·기본값, "컴포넌트 가이드"에
  `SttSliderField` 한 줄. "자동화 계약" 절(289행~)은 계약 변경이 없으므로 그대로.
- `docs/FILE_INDEX.md` — `SttSliderField.tsx` 신규 파일 1행 추가.
- 이 계획서 상단 상태 배너를 "완료"로 갱신.

`docs/API_SPEC.md` / `DELTA_PROTOCOL_SPEC.md` / `SCHEMA_CHANGES.md`는 **갱신 대상 아님** —
CLAUDE.md 연동표의 "배포 UI 계약 레이어"(`types/stt.ts`·`utils/deltaProtocol.ts`·`utils/wsUrl.ts`·
`constants/index.ts`·`api/**`)를 하나도 건드리지 않는다.

---

## 작업 방식

CLAUDE.md 규약상 main 브랜치에서 코드 편집이 hook으로 차단된다. 프런트 코드는 워크트리에서 작업한다.

```
git worktree add worktrees/ui-layout-settings -b feat/ui-layout-settings
cd worktrees/ui-layout-settings/frontend/app && pnpm install
```

`.venv` junction은 불필요하다(파이썬 코드를 건드리지 않음). 워크트리에서 작업하는 또 다른 이유는
`pnpm build`가 `emptyOutDir`로 `frontend/static/`을 비우기 때문 — main 체크아웃에서 빌드하면
경로 C 측정이 진행 중일 때 서빙 중인 dist를 날린다(CLAUDE.md §3.7).

---

## 검증

**A. 개발 서버 육안 검증** (워크트리에서 `pnpm dev`)

STT 서버 없이도 설정 드로어와 렌더 레이어를 확인할 수 있으나, 실제 블록이 필요하므로
백엔드를 띄우고 마이크(경로 B)로 몇 문장 전사한 뒤 확인한다:

1. 5개 항목 각각 슬라이더를 끝에서 끝까지 → 화면이 즉시 반응하는가
   - 좌우 여백: 0% ↔ 30%에서 텍스트 폭이 변하는가
   - 문단 간격: 블록↔블록만 벌어지고 원문/번역 사이는 안 변하는가
   - 문장 간격: 줄바꿈된 긴 문장의 줄간격 **과** 원문↔번역 간격이 **같이** 움직이는가
   - 번역 중 투명도: 1.0에서 미확정 회색 텍스트가 확정 텍스트와 동일한 밝기가 되는가.
     번역 대기 로더도 함께 진해지는가(pulse 애니메이션은 유지)
   - 하단 여백: 화면을 채운 상태에서 값을 올리면 **최신 전사가 화면 아래에서 띄워지는가**
2. 숫자 입력칸에 직접 타이핑 → 슬라이더가 따라오는가. 범위 밖(예: 투명도 `50`) 입력 시 clamp 되는가
3. 새로고침 → 값이 유지되는가 (localStorage `stt-theme-v2`)
4. "설정 초기화" → 5개 모두 기본값 복귀
5. 설정 드로어 열기/닫기 → 오른쪽 여백이 512px과 이중으로 밀리지 않는가
6. 자동 스크롤 회귀: 새 전사가 계속 들어올 때 바닥을 따라가는가 / 위로 스크롤하면 따라가기가
   멈추는가 / 다시 바닥으로 내리면 재개되는가 (`AUTOSCROLL_THRESHOLD_PX = 120`)

**B. 빌드·린트**

```
cd frontend/app && pnpm lint && pnpm build
```

**C. 측정 계약 회귀** (선택 — 경로 C 측정과 겹치지 않는 시점에)

`pnpm build` 후 배포 UI(`/wlkies/`)를 대상으로 `scripts/eval.py`를 짧은 파일 1개 `--repeat 1`로
돌려 하니스가 `stt-row` / `stt-text` / `data-trigger`를 정상 스크래핑하는지 확인한다. 이 변경은
STT 파이프라인을 건드리지 않으므로 **WER 수치 비교가 아니라 "스크래핑이 깨지지 않았는가"만** 본다.
다른 세션이 VBCable을 점유 중인지 먼저 확인한다.

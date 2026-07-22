# 경로 C 자동화 — 내장 UI → 배포 UI 전환 백로그

## 배경

2026-07-22 정책 확정(CLAUDE.md §3.3/§3.7, [docs/OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md) §5): 내장 UI
(`whisperlivekit/web/`) 사용을 중단하고 배포 UI(React, `frontend/app/`)를 경로 B/C를 포함한 모든 테스트
경로의 기본 UI로 삼는다.

서버 쪽 서빙 인프라는 이미 준비돼 있다 — `--frontend-dir`(기본값 `frontend/static`)·`--frontend-base`
(기본값 `auto`)가 `whisperlivekit/parse_args.py`에 정의돼 있고, `whisperlivekit/basic_server.py`가 dist
존재 여부만으로 내장/배포 UI를 자동 분기한다(`_frontend_enabled` 게이트). 이 저장소엔 이미 빌드 산출물
(`frontend/static/`)도 있어 서버만 놓고 보면 사실상 기본으로 배포 UI가 뜬다.

**막혀 있는 것은 자동화/스크래핑 레이어 하나뿐**이다. 경로 C가 실제로 브라우저를 조작하는
`scripts/vbcable_test.py::run_browser_test()`가 Playwright로 **내장 UI의 구체적 DOM**에 하드코딩돼 있다:

- `scripts/vbcable_test.py:137,140` — `page.wait_for_selector("#startButton")` / `page.click("#startButton")`
- `scripts/vbcable_test.py:193` — `page.click("#pauseButton")`
- `scripts/vbcable_test.py:197` — `page.text_content("#status")`에서 상태 문구("일시 중단됨"/"Finished processing" 등) 폴링
- `scripts/vbcable_test.py:145` — 전역 JS 변수 `websocket`(`window.websocket`) 존재로 연결 확인
- `scripts/vbcable_test.py:210-211` — `#linesTranscript .textcontent`에서 확정 문장 + `data-trigger` 속성 추출

배포 React UI(`frontend/app/`)엔 이 중 어떤 훅도 없다 — id도 `data-testid`도 없고(전수 grep 확인),
버튼은 텍스트 라벨만 있는 `<Button>시작</Button>` 형태이며, 상태 문구도 다르고("인식 중"/"일시 중단"/
"마무리 중" 등), WS 클라이언트는 `useSttSession.ts` 훅 안에 캡슐화돼 전역 변수가 없다. `finalize_trigger`는
데이터 모델(`frontend/app/src/types/stt.ts`, `utils/deltaProtocol.ts`)엔 있지만 DOM에 노출되지 않는다.

그래서 `scripts/eval.py`엔 이미 **정반대 방향의 우회 플래그**가 존재한다:

```python
# scripts/eval.py:667-670
parser.add_argument(
    "--server-frontend-dir", ...,
    dest="server_frontend_dir",
    help="서버에 전달할 --frontend-dir 오버라이드. 로컬에 frontend/static React dist가 있으면 GET /가 그쪽으로 "
    "리다이렉트돼 eval.py의 Playwright 레거시 UI(#startButton) 테스트가 깨진다 — 빈 디렉터리(예: .omc/eval_empty_frontend)를 "
    "지정해 레거시 내장 UI로 강제 폴백시킬 때 사용.",
)
```

즉 지금은 "배포 UI가 있으면 깨지니 내장 UI로 강제 폴백시키는" 임시 우회가 기본 상태이고, 이번 문서 갱신
(2026-07-22)에서는 이 우회를 **모든 경로 C 안내 문서(docs/TESTING.md, .claude/commands/eval.md,
docs/DEPLOYMENT_OFFLINE.md §4.1/§4.4/§8)에 "과도기 조치"로 명시**했다. 이 백로그는 그 과도기를 끝내는
실제 구현 작업을 담는다.

## 필요 작업

1. **`scripts/vbcable_test.py::run_browser_test()`를 배포 UI(React) DOM 대상으로 재작성**
   - 시작/일시중단/종료 버튼: id/`data-testid`가 없으므로 텍스트 라벨 매칭(`get_by_text` 등) 또는 2번 작업으로
     안정적 훅을 먼저 추가.
   - 상태 폴링: React 쪽 상태 문구(`SttSettingDrawer.tsx`의 `phaseLabel()` — "인식 중"/"일시 중단"/"마무리 중"
     등)로 폴링 로직 교체. 내장 UI 문구("일시 중단됨"/"Finished processing" 등)와 다르므로 그대로 재사용 불가.
   - 확정 문장 추출: `SttTextViewer.tsx`가 렌더링하는 확정 줄에 안정적 선택자가 없음 — 2번 작업 필요.
   - `finalize_trigger` 진단 수집: 데이터 모델(`types/stt.ts`, `deltaProtocol.ts`)엔 있으나 DOM에 노출되지
     않음 — 유지하려면 2번 작업으로 `data-trigger` 속성 노출 필요(전사 txt의 `[문장별 확정 트리거]` 섹션·
     JSON `hyp_lines[].trigger`가 이 값에 의존, `docs/TESTING.md` 경로 C 절 참조).
   - `window.websocket` 전역 변수 대체: `useSttSession.ts` 훅 내부 상태이므로 연결 확인 방식을 바꿔야 함
     (예: 네트워크 이벤트 관찰, 혹은 2번 작업으로 노출용 훅 추가).

2. **React 쪽(`frontend/app/src/components/SttSettingDrawer.tsx`, `SttTextViewer.tsx` 등) 최소 자동화 훅
   추가 여부 결정** — `data-testid`(버튼·확정 줄), `data-trigger`(확정 트리거) 등. **CLAUDE.md §3.7에 따라
   React 측 변경은 먼저 [docs/OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md) §5에서 논의해 결정**한다(임의로 먼저
   구현하지 않는다).

3. **`scripts/eval.py`의 `--server-frontend-dir` 플래그 의미 재정립** — 배포 UI가 기본이 되면 이 플래그는
   현재와 반대로 "내장 UI로 강제 폴백(레거시/디버그용)"이라는 의미로 존속하거나, 더 이상 쓸 일이 없으면
   폐지를 검토한다. 어느 쪽이든 `--server-frontend-dir` 관련 문서(docs/TESTING.md, .claude/commands/eval.md,
   docs/DEPLOYMENT_OFFLINE.md)의 "과도기" 문구를 함께 갱신해야 한다.

4. **`closed_test.py` 동반 검증** — `docs/DEPLOYMENT_OFFLINE.md` §4.1이 명시하듯 `closed_test.py`는
   `scripts/eval.py`/`vbcable_test.py`의 서버 기동·VBCable 재생·metric 함수를 재사용하므로 위 1~3번 작업이
   끝나면 폐쇄망 자동측정 경로도 함께 재검증한다(§4.1/§4.4 상호작용 — dist 배치 후 자동측정이 깨지지 않는지).

5. **구현 완료 후 문서 갱신** — 이번(2026-07-22) 문서 갱신에서 "과도기"·"구현 공백"·"강제 폴백" 문구를 넣은
   모든 위치를 "완료"로 되돌린다. 체크리스트:
   - [ ] `CLAUDE.md` §3.3 (내장 UI 과도기 언급 제거)
   - [ ] `docs/TESTING.md` 경로 C 절 (과도기 조치 문단 제거, `--server-frontend-dir` 안내 갱신)
   - [ ] `.claude/commands/eval.md` (UI 방침 콜아웃 + 예시 커맨드의 `--server-frontend-dir .omc/eval_empty_frontend` 제거)
   - [ ] `docs/DEPLOYMENT_OFFLINE.md` §4.1/§4.4/§8 (과도기 경고·트러블슈팅 행 제거 또는 갱신)
   - [ ] `docs/FILE_INDEX.md` (vbcable_test.py 각주 갱신)
   - [ ] `docs/OPEN_QUESTIONS.md` §5 ("구현 대기" → "해소"로 갱신)

## 진행 방식

이 문서는 분석·설계 제안까지만 담는다([docs/backlog/README.md](README.md) 규약). 실측 없이 구현하지
않으며, 착수 시 별도 goal 프롬프트([docs/goal_prompt/](../goal_prompt/))로 분리해 진행한다.

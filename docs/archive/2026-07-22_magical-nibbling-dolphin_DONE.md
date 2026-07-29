# 계획: UTF-8 반토막 음절이 디코더 컨텍스트를 오염시키는 근본원인 수정 (한국어 중간 단어 유실)

## Context — 왜 이 작업을 하는가

배포 PC에서 **한 화자가 코드스위칭 없이 이어 말하는데 중간 단어가 통째로 유실**되는 현상이 보고됐다("중동전쟁"→"중쟁", "플랫폼을 구축하는"→"구축하는"). 이번 세션에서 kor1~3+sbs1 각 5회(경로 C, `--trace-tokens`)를 측정·분석해 원인을 바이트 단위까지 확정했고, 이미 머지된 seam 수정(`SEAM_CONVERGENCE_FIX_ENABLED`)이 **일부만** 잡고 잔존 유실이 남아있음을 확인했다.

**확정된 단일 근본원인**: Whisper의 byte-level BPE는 한글 1글자(UTF-8 3바이트)를 최대 3토큰에 흩뿌린다. AlignAtt 스트리밍이 음절 중간에서 배치를 커밋하면 그 배치의 마지막 토큰이 반토막(디코드 시 U+FFFD `�`)이 된다. 방출 경로(`_build_timestamped_words`)와 hold 경로(`_handle_pending_tokens`)는 seam 수정으로 이미 "첫 `�` 단어"에서 멈추도록 정렬됐지만, **커밋 경로만 여전히 `�`를 넘어 전진한다**:

1. `align_att_base.py:869` `self.state.tokens.append(new_tokens_tensor)` — `new_hypothesis`(반토막 `�` 토큰 포함 가능)를 디코더 컨텍스트에 커밋.
2. 다음 청크는 `token_len_before`(:757) high-water mark **뒤쪽**만 재디코딩 → 커밋된 반토막 음절은 mark에 묻혀 영영 재디코딩 안 됨.
3. hold된 완성 바이트는 재디코딩이 이어바이트를 안 주면(오염된 컨텍스트가 모델을 음절 건너뛰게 만듦) `MAX_PENDING_RETRIES=2` 소진 후 드롭(:1022) — 이 드롭은 seam 플래그로 **안 막힌다**.

결과: 앞바이트는 커밋돼 mark를 전진시켰는데 완성분은 드롭 → 음절/단어 영구 유실. 두 조사 에이전트가 독립 추적한 "사령관은"→"관점"(2/5)과 "보장하고 예비"→소실(3/5)·"로봇 등 유무인"→소실(2/5)이 **전부 이 하나의 뿌리**로 수렴했다.

**의도한 결과**: 반토막 음절을 커밋에서 제외해 high-water mark를 깨끗이 유지 → 다음 청크가 그 오디오 구간을 **깨끗한 컨텍스트에서 재디코딩**해 온전한 단어를 생성 → 이미 있는 seam 게이트가 stale 반토막을 정리. 트레이드오프 없는 순이득이 목표(순수 방출/커밋 계층 정합성 수정).

## 범위 (사용자 확정)

- **집중**: UTF-8 반토막 뿌리 하나. (사령관은/보장하고/로봇 모두 동일 뿌리.)
- **측정 포함**: kor1~3(`--lan ko`) + sbs1·**bong1·ytn2**(`--lan auto`) — seam 수정이 bong1/ytn2를 안 보고 머지됐으므로 §3.8 최우선 파일 회귀도 함께 확인.
- **범위 밖(계획서에 명시만)**: kor1 "전자기"→"전작이"는 무로그 모델 앰비귀티(반토막 아님, hold/커밋 경로 미진입) — 이 수정으로 못 잡음. BUG A(침묵 후 유실)는 별개 패밀리.

## 접근 — 클린 커밋 절단 (Direction A)

커밋 직전 `new_hypothesis`를 **첫 `�` 단어 앞의 클린 프리픽스로 절단**한다. 순수 subtractive(길이를 늘리지 않음) — 비-fire "마지막 단어 hold" 스트리밍 의미 불변. 대안(바이트 단위 고아 재결합)은 교차배치 바이트 상태+짝짓기 휴리스틱이 필요해 복잡도↑·mojibake 위험, 기각.

**핵심 검증 (에이전트가 코드로 확인)**: 오디오 위치는 토큰 커밋과 분리돼 있다 — 버퍼는 `insert_audio`에서 `audio_max_len`(20s) 초과 시 **앞쪽(오래된)만** 트림된다(`simul_whisper.py:167`). 반토막 음절은 버퍼 **끝**(fire 경계)에 있어 앞-트림 대상이 아니다. 따라서 토큰을 커밋 안 해도 그 오디오는 버퍼에 남고, 다음 `infer()`가 짧아진 프리픽스로 그 구간을 깨끗이 재디코딩한다. PyTorch(`SimulWhisper`)·MLX(`MLXAlignAtt`) 둘 다 베이스 `infer()` 상속 → **한 곳 수정으로 양 백엔드 커버**.

## 수정할 파일

### `whisperlivekit/simul_whisper/align_att_base.py`

1. **롤백 플래그** (기존 `SEAM_CONVERGENCE_FIX_ENABLED` 옆 ~:51):
   ```python
   CONTEXT_CLEAN_COMMIT_ENABLED = True  # False = 완전 기존 동작 — 짝지음 A/B 롤백 플래그
   ```
   주석에 `SEAM_CONVERGENCE_FIX_ENABLED=True`와 함께 동작함을 명시(게이트가 stale 반토막 정리 담당).

2. **새 헬퍼** `_clean_commit_hypothesis(self, new_hypothesis, split_words, split_tokens)` — `_split_tokens`(끝 :937) 뒤에 삽입. 첫 `�` 단어 인덱스를 찾아(기존 `_handle_pending_tokens`의 `�` 검출 idiom 재사용, 새 tokenizer 호출·재디코딩 없음) 그 앞까지의 토큰만 반환. `incomplete_idx is None`이면 원본 그대로. `len(clean_prefix) < len(new_hypothesis)`일 때만 절단(둘 다 같은 순서 리스트의 프리픽스라 짧은 쪽이 교집합).
   - fire/is_last 분기: `clean_prefix ≤ new_hypothesis(=전체)` → `�` 이후 제외 ✅
   - 비-fire·`�`가 마지막: no-op(이미 `new_hypothesis`에서 제외됨) ✅
   - 비-fire·`�` 중간: 절단(hold-from-first-`�` 계약과 일치) ✅

3. **호출 지점** :868-870 — `new_hypothesis` 대신 `commit_hypothesis = self._clean_commit_hypothesis(...)`로 텐서 생성·커밋·`Output:` 로그. `_quality_gate`(:863-864)는 원본 `new_hypothesis` 유지(억제 판정은 전체 청크 기준, 절단은 컨텍스트 위생). 빈 텐서 커밋은 기존에도 발생하는 안전 경로(비-fire 단일단어 :936).

### `whisperlivekit/simul_whisper/simul_whisper.py` · `mlx/simul_whisper.py`
읽기 전용 검증만 — `_make_new_tokens_tensor([])`가 빈 커밋 허용(`:524`/mlx `:418`), `trim_context`/`_current_tokens`가 zero-width 텐서 허용 확인. **코드 편집 없음**(베이스 `infer()` 상속).

## TDD — `tests/test_utf8_held_emission.py` 확장

기존 헬퍼 재사용(`make_decoder`·`run_chunk`·`FFFD`·`aab` monkeypatch). thin 헬퍼 `commit_prefix(fs, tokens, fire_detected, is_last)` 추가(=`_split_tokens`→`_clean_commit_hypothesis` 언바운드 호출).

**신규 RED**(수정 전 실패→후 통과):
- `test_commit_excludes_trailing_incomplete_syllable` — fire, `" 구축하는"+" 방어�"` → `committed == encode(" 구축하는")`, `FFFD not in decode(committed)`.
- `test_commit_halts_at_first_fffd_midposition` — fire, 중간 `�`: `" 보장하고"+"방어�"+" 예비"` → split 전제 확인 후 `committed == encode(" 보장하고")`.
- `test_commit_empty_when_only_incomplete_word` — `"미�"`만 → `committed == []`.

**A/B 플래그**: `test_flag_false_commits_broken_token` — `monkeypatch CONTEXT_CLEAN_COMMIT_ENABLED=False` → `committed == tokens`(pre-fix 재현).

**무회귀**: `test_commit_unchanged_when_all_clean`·`test_commit_nonfire_lastword_unchanged`(subtractive 증명).

**복구 통합**: `test_full_redecode_supersedes_stale_pending_single_emit` — 청크1이 `미�` hold+커밋 0 → 청크2가 전체 `미디어` 재디코딩 → seam 게이트가 stale 반토막 discard → `emitted == ["미디어"]`, 중복 0.

**반드시 GREEN 유지(수정 금지)**: `test_media_no_leading_fragment_duplication`(:265, "미 미디어" 중복 가드) + H1~H4·기존 `test_flag_false_*` 13개 전부. 이번 편집은 커밋 경로만 건드리고 `run_chunk`가 그 경로를 안 타므로 구조상 무영향.

게이트: `.venv\Scripts\python.exe -m pytest tests/ -q` 전량 GREEN, `.venv\Scripts\ruff.exe check .` clean(line-length 120). **`uv run`/`uv sync` 금지**(공유 venv 가드레일).

## 측정 (경로 C, diar-ON Sortformer CRT=3.0, turbo, `--trace-tokens`)

`scripts/eval.py`, 포트 8901, 짝지음 ON/OFF(`CONTEXT_CLEAN_COMMIT_ENABLED` 토글, `SEAM_CONVERGENCE_FIX_ENABLED=True` 유지). `--lan`은 run당 1값 → 모드별 run 분리:
- ko: `--files kor1 kor2 kor3 --lan ko`
- auto: `--files sbs1 bong1 ytn2 --lan auto`

**표적 지표(before/after, ON/OFF)**:
- `[UTF-8 Fix] Dropping … after 2 retries` 이벤트 수 → 0 방향 기대. `Holding`/`Prepending`/seam `Discarding stale`도 라벨 분류(복구/유실/손상/중복).
- 정답 `test_data/<name>.txt` 대비 알려진 유실구 존재 여부: `사령관은`·`보장하고 예비`·`로봇 등 유무인`(+sbs1 `플랫폼`). 기준선 재현 빈도 = 사령관은 2/5·보장하고 3/5·로봇 2/5.
- WER/화자F1/문장F1은 `--repeat 1`에선 방향신호. **hard 게이트: Case B 0 + "미 미디어"류 중복 0.** 순수 정합성 수정이라 worst-case 미회귀가 판정 기준.

**측정 = 스크리닝 1회만**(사용자 시간제약 지시 — `--repeat 3` 확정측정 단계 제외). 스크리닝에서 ①표적지표(Dropping 이벤트·알려진 유실구) 개선 ②Case B·중복 0 ③catastrophic 회귀 없음이면 **성공 판단 → 커밋**. 1회 수치의 방향신호 한계는 인지하되, 순수 커밋-계층 정합성 수정 + 단위테스트로 로직이 고정돼 있어 회차편차 리스크가 낮은 성격임을 근거로 커밋 판단(seam 수정과 동일 규율).

**워크트리·산출물 규약(지난 사고 방지)**:
- 워크트리 `.venv`는 메인에 Junction(`mklink /J`). import가 워크트리로 해석되는지 확인 후 cwd=워크트리에서 측정.
- **워크트리 삭제 전 `.omc/` 산출물(전사·JSON·로그)을 워크트리 밖으로 복사**. `git worktree remove --force`가 gitignore 산출물을 지운다(이번 세션에 seam A/B 파일 소실 발생).
- **워크트리 삭제 전 `.venv` Junction을 먼저 `cmd /c rmdir .venv`로 해제**(정션 따라가 메인 `.venv` 재삭제되는 사고 방지 — 이번 세션 2회 발생).

## 검증 (end-to-end)

1. 단위: `.venv\Scripts\python.exe -m pytest tests/test_utf8_held_emission.py -q` — 신규 RED가 수정 후 GREEN, 기존 13개 유지. 이어 `pytest tests/ whisperlivekit/ -q`(워크트리 재귀수집 회피 위해 경로 명시) 전량 GREEN.
2. 짝지음 A/B(위 측정, **스크리닝 1회만**) — ON에서 `Dropping` 이벤트·알려진 유실구가 OFF 대비 감소, Case B·중복 0 확인. 성공 판단 시 커밋(확정 `--repeat 3` 단계 없음).
3. 정성: ON/OFF 전사 대조로 복구 사례 before/after 인용, 신규 중복/환각 부작용 없음 확인.

## 산출물 · 채택

- 브랜치 `exp/utf8-context-clean-commit`(신규 워크트리) 구현 → **스크리닝 1회 + 정성 확인**에서 성공 판단이면 커밋. `--repeat 3` 확정측정 단계는 시간제약으로 생략(사용자 지시).
- master 머지는 seam 때와 동일하게 **커밋 후 사용자 확인** 절차(§4 "목표 필수 기능 채택은 사용자 질의"). 스크리닝만 근거임을 머지 판단 시 명시.
- `/log-experiment`로 Exp-200 기록(측정 모드 ko+auto, 스크리닝 1회 근거임 명시). 문장확정 로직 무관이라 `SENTENCE_FINALIZATION_LOGIC.md` 갱신 원칙적 불필요.

## 복구 상황 (사용자 우려 대응)

- **온전(핵심)**: 원본 5회 진단 측정 전체 — kor1~3+sbs1 각 5회 전사 + `--trace-tokens` 로그 22개 + 벤치마크 JSON 2개(`.omc/`에 그대로). 모든 유실 버그 원자료 보존.
- **소실(경미·재생성)**: seam ON/OFF 비교 파일만(gitignore+워크트리 삭제+휴지통 미경유 → 일반 복구 불가). 위 측정에 bong1/ytn2 포함 재측정이 사실상 이 데이터의 상위호환 복구.

## 미해결 잔존 (범위 밖 — 후속)

- kor1 "전자기"→"전작이": 무로그 모델 앰비귀티(반토막 아님) — 이 수정 미적용, 별도 조사 필요.
- BUG A(침묵/세션시작 유실): 긴침묵 완전리셋 콜드스타트 등 3~4갈래 — `docs/research/2026-07-22_kor-silence-wordloss-diagnostic.md`에 정리됨, 별도 이터레이션.
- 희귀: 반토막 오디오가 20s 창 밖으로 트림되기 전 재디코딩 못하면 기존 드롭 폴백(빈도 大 감소, 회귀 아님).

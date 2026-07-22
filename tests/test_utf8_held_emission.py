# -*- coding: utf-8 -*-
"""held/UTF-8 재조립 방출 계층 유실 수정(Exp-191) 단위 테스트.

배포 제보(동일 화자 연속 발화 중 단어 유실: "중동전쟁"→"중쟁",
"이러한 플랫폼을 구축하는"→"이러한 구축하는")의 원인 2종을 고정한다:

- H1 (계약 불일치): _build_timestamped_words는 루프 내 **모든 위치**의 U+FFFD 단어를
  skip하는데 _handle_pending_tokens는 **마지막 단어만** hold → 중간 위치 U+FFFD 단어가
  방출도 hold도 안 되고 영구 유실. 수정 = 첫 U+FFFD 단어에서 방출 중단(break) +
  첫 U+FFFD부터 전부 hold(계약 정렬).
- H2 (생성원): 스테일 pending 재-prepend가 phantom 중간 U+FFFD를 생성 — held orphan
  바이트 + 재-디코드 토큰이 무공백으로 한 단어로 묶여 구 전체가 skip-소멸(mojibake
  누적 포함, sbs1 실측 "방어�어�이라는어�"). 수정 = seam 수렴 게이트:
  decode(pending+new)에 U+FFFD가 있는데 decode(new) 단독은 clean이면 스테일 판정 →
  pending 폐기, new만 정상 처리.

회귀 제약(hard): Exp-087의 "미 미디어" 선두조각 중복 수정(부분 방출 금지 + hold/재시도)
은 유지돼야 한다 — 정상 이어받기(미디어형)는 new 단독 decode도 U+FFFD(continuation
바이트)라 게이트가 발동하지 않는다.

전부 순수 로직 계층 — 실제 tokenizer(tiktoken, 오프라인)만 쓰고 모델 없이 검증한다
(test_case1_expB.py 패턴: SimpleNamespace state + AlignAttBase 언바운드 메서드).
"""

import types
from types import SimpleNamespace

import pytest

import whisperlivekit.simul_whisper.align_att_base as aab
from whisperlivekit.simul_whisper.align_att_base import AlignAttBase
from whisperlivekit.whisper import tokenizer as whisper_tokenizer

FFFD = "�"

# ─── 픽스처 / 헬퍼 ────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def tk():
    """실제 multilingual tokenizer (torch/모델 불필요 — tiktoken+assets만)."""
    return whisper_tokenizer.get_tokenizer(
        multilingual=True, language="ko", num_languages=99, task="transcribe"
    )


def make_decoder(tk):
    """AlignAttBase(ABC) 메서드를 바인딩할 최소 상태의 가짜 디코더."""
    fs = SimpleNamespace(
        tokenizer=tk,
        state=SimpleNamespace(
            pending_incomplete_tokens=[],
            pending_retries=0,
            speaker=-1,
            detected_language="ko",
            global_time_offset=0.0,
        ),
    )
    return fs


def merge_pending(fs, new_tokens):
    """infer() post-decode의 pending prepend 지점 재현.

    수정 후엔 _merge_pending_tokens(seam 게이트 포함)를 쓰고, 수정 전(메서드 부재)엔
    기존 라인 474-479의 무조건 prepend를 재현한다 — "미 미디어" 회귀 테스트가
    수정 전에도 GREEN이어야 하므로 버전 무관 헬퍼로 둔다.
    """
    if hasattr(AlignAttBase, "_merge_pending_tokens"):
        return AlignAttBase._merge_pending_tokens(fs, new_tokens)
    pending = fs.state.pending_incomplete_tokens
    return pending + new_tokens if pending else new_tokens


def run_chunk(fs, new_tokens):
    """infer() post-decode 경로 축약 재현: merge → split → build → handle.

    반환 = 이번 청크에 방출된 단어 텍스트 리스트.
    """
    tokens = merge_pending(fs, new_tokens)
    split_words, split_tokens = fs.tokenizer.split_to_word_tokens(tokens)
    timestamps = [i * 0.1 for i in range(len(tokens) + 1)]
    words = AlignAttBase._build_timestamped_words(fs, split_words, split_tokens, timestamps)
    AlignAttBase._handle_pending_tokens(fs, split_words, split_tokens)
    return [w.text for w in words]


def build_and_handle(fs, tokens):
    """merge 없이 build+handle만 — 게이트를 우회해 계약 정렬(변경 A) 단독 검증용."""
    split_words, split_tokens = fs.tokenizer.split_to_word_tokens(tokens)
    timestamps = [i * 0.1 for i in range(len(tokens) + 1)]
    words = AlignAttBase._build_timestamped_words(fs, split_words, split_tokens, timestamps)
    AlignAttBase._handle_pending_tokens(fs, split_words, split_tokens)
    return [w.text for w in words]


# ─── H1: 중간 위치 U+FFFD 단어 계약 정렬 (변경 A) ─────────────────────────────


def test_h1_mid_fffd_halts_emission_and_holds_from_first_fffd(tk):
    """중간 U+FFFD 단어("방어�")는 첫 U+FFFD에서 방출 중단 + 거기서부터 전부 hold.

    수정 전: build가 "방어�"만 skip하고 " 구축하는"을 방출, handle은 마지막 단어
    (완성)만 보고 pending 클리어 → "방어" 영구 유실·재시도 0 (RED).
    수정 후: 이번 청크 무방출, [방어� + 구축하는] 토큰 전부 hold·다음 청크 이연.
    (실전에선 이 입력 대부분을 H2 seam 게이트가 선차단하지만, 게이트 미발동 경로
    — 예: new 단독 decode에 U+FFFD가 있는 경우 — 의 안전망 계약이다.)
    """
    fs = make_decoder(tk)
    held = tk.encode("방어선이라는")[:2]  # decode = "방어�" (어+선의 첫 바이트)
    tokens = held + tk.encode(" 구축하는")
    # split = ["방어�", " 구축하는"] — 중간 위치 U+FFFD
    emitted = build_and_handle(fs, tokens)
    assert emitted == [], f"첫 U+FFFD 이후 단어가 방출됨(이연 실패): {emitted}"
    assert fs.state.pending_incomplete_tokens == tokens, (
        f"첫 U+FFFD부터 전부 hold돼야 함: {fs.state.pending_incomplete_tokens}"
    )
    assert fs.state.pending_retries == 1


def test_h1_last_word_fffd_unchanged(tk):
    """U+FFFD가 마지막 단어에만 있는 흔한 경우는 현행과 동일 거동(hold·무방출 아님).

    선행 clean 단어는 방출되고 마지막 미완성 단어만 hold된다.
    """
    fs = make_decoder(tk)
    tail = tk.encode(" 방어선이라는")[:2]  # decode = " 방어�" (선행공백 → 별도 단어)
    tokens = tk.encode(" 구축하는") + tail  # [" 구축하는", " 방어�"]
    emitted = build_and_handle(fs, tokens)
    assert emitted == [" 구축하는"]
    assert fs.state.pending_incomplete_tokens == tail
    assert fs.state.pending_retries == 1


# ─── H2: seam 수렴 게이트 (변경 B) ────────────────────────────────────────────


def test_h2_stale_seam_discards_pending_and_emits_fresh(tk):
    """스테일 seam: held "방어�" + 재-디코드 "선이라는"(단독 clean) → pending 폐기.

    수정 전: 무조건 prepend → "방어�선이라는" 한 단어(무공백) → 통째 skip →
    구 전체 소멸. 수정 후: 게이트가 스테일 판정(merged에 U+FFFD, new 단독 clean),
    pending 폐기 + fresh "선이라는"만 정상 방출.
    """
    fs = make_decoder(tk)
    fs.state.pending_incomplete_tokens = tk.encode("방어선이라는")[:2]
    fs.state.pending_retries = 1
    emitted = run_chunk(fs, tk.encode("선이라는"))
    assert emitted == ["선이라는"], f"fresh 구가 유실됨: {emitted}"
    assert fs.state.pending_incomplete_tokens == []
    assert fs.state.pending_retries == 0


def test_h2_gate_not_fired_on_legitimate_continuation(tk):
    """정상 이어받기(미디어형)는 게이트 미발동 — new 단독 decode도 U+FFFD.

    held "미�" + continuation 바이트 → prepend 유지 → 완성 단어 "미디어" 방출.
    """
    fs = make_decoder(tk)
    media = tk.encode("미디어")
    fs.state.pending_incomplete_tokens = media[:2]
    fs.state.pending_retries = 1
    emitted = run_chunk(fs, media[2:])
    assert emitted == ["미디어"]
    assert fs.state.pending_incomplete_tokens == []


def test_h2_gate_not_fired_on_empty_new_tokens(tk):
    """이번 청크 무토큰(new=[])이면 게이트 미발동 — 현행 유지(pending 그대로 재시도)."""
    fs = make_decoder(tk)
    held = tk.encode("미디어")[:2]
    fs.state.pending_incomplete_tokens = list(held)
    fs.state.pending_retries = 1
    emitted = run_chunk(fs, [])
    assert emitted == []
    # 무토큰 청크에선 마지막(유일) 단어가 여전히 U+FFFD → 계속 hold(재시도 1회 소진)
    assert fs.state.pending_incomplete_tokens == held
    assert fs.state.pending_retries == 2


def test_h2_mojibake_does_not_accumulate(tk):
    """스테일 pending 반복 재-prepend로 인한 U+FFFD(mojibake) 누적이 게이트로 차단됨.

    수정 전: 매 라운드 "방어�선이라는..." 한 단어로 묶여 통째 skip·재hold →
    retry 소진까지 fresh 구가 연속 소멸(3라운드 중 1회만 방출). 수정 후:
    첫 라운드에 스테일 폐기 → 매 라운드 fresh 구가 온전히 방출, U+FFFD 방출 0.
    """
    fs = make_decoder(tk)
    fs.state.pending_incomplete_tokens = tk.encode("방어선이라는")[:2]
    fs.state.pending_retries = 1
    emitted = []
    for _ in range(3):  # 재-디코드가 매번 같은 스테일 구를 내놓는 시나리오
        emitted += run_chunk(fs, tk.encode("선이라는"))
    assert all(FFFD not in t for t in emitted), f"mojibake 방출: {emitted}"
    assert emitted.count("선이라는") == 3, f"fresh 구 유실: {emitted}"
    assert fs.state.pending_incomplete_tokens == []


# ─── H3: 상한 로직 현행 유지 ──────────────────────────────────────────────────


def test_h3_retry_exhaustion_drops_pending(tk):
    """MAX_PENDING_RETRIES(2) 소진 시 pending drop — 현행 거동 유지."""
    fs = make_decoder(tk)
    held = tk.encode("미디어")[:2]  # ["미�"] — 마지막 단어 U+FFFD
    build_and_handle(fs, held)
    assert fs.state.pending_retries == 1
    assert fs.state.pending_incomplete_tokens == held
    build_and_handle(fs, held)
    assert fs.state.pending_retries == 2
    build_and_handle(fs, held)  # 3회째 — 소진
    assert fs.state.pending_incomplete_tokens == []
    assert fs.state.pending_retries == 0


def test_h3_token_limit_drops_pending(tk):
    """hold 대상이 MAX_PENDING_TOKENS(10) 초과면 drop — 현행 거동 유지."""
    fs = make_decoder(tk)
    # 합성 split: U+FFFD 단어 하나가 11토큰 (환각 의심 케이스)
    split_words = [f"환각{FFFD}"]
    split_tokens = [list(range(11))]
    AlignAttBase._handle_pending_tokens(fs, split_words, split_tokens)
    assert fs.state.pending_incomplete_tokens == []
    assert fs.state.pending_retries == 0


# ─── H4: refresh/reset의 pending 클리어 거동 고정 ─────────────────────────────


def test_h4_decoder_state_reset_clears_pending():
    """DecoderState.reset()은 pending을 무조건 클리어한다 — 거동 고정(유지)."""
    from whisperlivekit.simul_whisper.decoder_state import DecoderState

    st = DecoderState()
    st.pending_incomplete_tokens = [1, 2, 3]
    st.pending_retries = 2
    st.reset()
    assert st.pending_incomplete_tokens == []
    assert st.pending_retries == 0


def test_h4_refresh_segment_clears_pending(tk):
    """refresh_segment()도 hold 중 pending을 무조건 클리어한다 — 거동 고정(유지)."""
    fs = make_decoder(tk)
    fs.state.segments = []
    fs.state.context = None
    fs.state.cumulative_time_offset = 0.0
    fs.state.log_segments = 0
    fs.state.last_attend_frame = 0
    fs.state.pending_incomplete_tokens = [1, 2]
    fs.state.pending_retries = 1
    fs.cfg = SimpleNamespace(rewind_threshold=200)
    fs.init_tokens = lambda: None
    fs.init_context = lambda: None
    fs._stage1_shadow_reset_evidence = lambda: None  # master 머지(Exp-197 계측)로 refresh_segment가 호출
    fs.segments_len = types.MethodType(AlignAttBase.segments_len, fs)
    AlignAttBase.refresh_segment(fs, complete=True)
    assert fs.state.pending_incomplete_tokens == []
    assert fs.state.pending_retries == 0


# ─── "미 미디어" 회귀 (Exp-087, 최중요 — 수정 전/후 모두 GREEN) ────────────────


def test_media_no_leading_fragment_duplication(tk):
    """정상 이어받기 2청크: clean "미디어" 정확히 1회 방출, "미" 단독 방출 0.

    Exp-087이 고친 선두조각 중복("미 미디어")의 회귀 가드 — 부분 방출 금지 +
    hold/재시도 방출이 수정 전에도, 수정 후에도 동일하게 유지돼야 한다.
    """
    fs = make_decoder(tk)
    media = tk.encode("미디어")
    emitted = run_chunk(fs, media[:2])  # chunk1: "미�" — hold, 무방출
    assert emitted == []
    assert fs.state.pending_incomplete_tokens == media[:2]
    emitted += run_chunk(fs, media[2:])  # chunk2: continuation prepend → 완성
    assert emitted == ["미디어"], f"선두조각 중복/유실: {emitted}"
    assert "미" not in emitted
    assert fs.state.pending_incomplete_tokens == []


# ─── 롤백 플래그 False = 완전 기존 동작 ───────────────────────────────────────


def test_flag_false_reproduces_h1_loss(tk, monkeypatch):
    """SEAM_CONVERGENCE_FIX_ENABLED=False면 H1 유실이 그대로 재현된다(기존 동작).

    A/B 짝지음 측정용 롤백 경로 검증: build가 중간 "방어�"만 skip하고
    " 구축하는"을 방출, handle은 pending을 클리어(hold 없음)한다.
    """
    monkeypatch.setattr(aab, "SEAM_CONVERGENCE_FIX_ENABLED", False, raising=False)
    fs = make_decoder(tk)
    tokens = tk.encode("방어선이라는")[:2] + tk.encode(" 구축하는")
    emitted = build_and_handle(fs, tokens)
    assert emitted == [" 구축하는"]
    assert fs.state.pending_incomplete_tokens == []
    assert fs.state.pending_retries == 0


def test_flag_false_disables_seam_gate(tk, monkeypatch):
    """플래그 False면 seam 게이트도 없음 — 스테일 pending이 기존처럼 재-prepend된다."""
    monkeypatch.setattr(aab, "SEAM_CONVERGENCE_FIX_ENABLED", False, raising=False)
    fs = make_decoder(tk)
    held = tk.encode("방어선이라는")[:2]
    fs.state.pending_incomplete_tokens = list(held)
    fs.state.pending_retries = 1
    new = tk.encode("선이라는")
    merged = merge_pending(fs, new)
    assert merged == held + new, "플래그 False에서 prepend가 억제됨(기존 동작 아님)"
    assert fs.state.pending_incomplete_tokens == held

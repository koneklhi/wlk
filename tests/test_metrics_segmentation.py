"""whisperlivekit.metrics.compute_segmentation 유닛 테스트."""
from whisperlivekit.metrics import (
    _align_ops,
    _align_words,
    compute_segmentation,
    compute_speaker_sentence_segmentation,
    compute_wer,
)


def test_perfect_segmentation():
    ref = ["the cat sat", "on the mat", "it was warm"]
    hyp = ["the cat sat", "on the mat", "it was warm"]
    r = compute_segmentation(ref, hyp)
    assert r["f1"] == 1.0
    assert r["precision"] == 1.0
    assert r["recall"] == 1.0
    assert r["ref_sentences"] == 3
    assert r["hyp_sentences"] == 3


def test_under_segmentation():
    # 가설이 3문장을 1문장으로 합침 → 경계 0개 → recall 0
    ref = ["the cat sat", "on the mat", "it was warm"]
    hyp = ["the cat sat on the mat it was warm"]
    r = compute_segmentation(ref, hyp)
    assert r["recall"] == 0.0
    assert r["hyp_sentences"] == 1


def test_over_segmentation():
    # 가설이 1문장을 3개로 쪼갬 → 정답 경계 0개 → precision 0
    ref = ["the cat sat on the mat it was warm"]
    hyp = ["the cat sat", "on the mat", "it was warm"]
    r = compute_segmentation(ref, hyp)
    assert r["precision"] == 0.0


def test_tolerance_with_asr_error():
    # 단어 오류가 있어도 경계 위치가 ±1 이내면 매칭
    ref = ["the cat sat", "on the mat"]
    hyp = ["the cat sat", "in the mat"]  # on→in 치환
    r = compute_segmentation(ref, hyp)
    assert r["f1"] == 1.0


def test_partial_boundary_match():
    ref = ["a b c", "d e f", "g h i"]      # 경계 @3, @6
    hyp = ["a b c d e f", "g h i"]          # 경계 @6 만
    r = compute_segmentation(ref, hyp)
    assert r["matched_boundaries"] == 1
    assert r["recall"] == 0.5
    assert r["precision"] == 1.0


def test_korean_english_mixed():
    ref = ["안녕 하세요", "thank you minister", "감사 합니다"]
    hyp = ["안녕 하세요", "thank you minister", "감사 합니다"]
    r = compute_segmentation(ref, hyp)
    assert r["f1"] == 1.0


# ── _align_words / _align_ops 무동작 리팩터링 회귀 가드 ─────────────────────
#
# _align_words의 DP+backtrace 본문은 _align_ops로 이동했고 _align_words는 그 결과에서
# hyp_to_ref만 재구성한다. 정렬 결과가 조금이라도 달라지면 compute_segmentation·
# compute_speaker_sentence_segmentation의 기존 F1 수치가 통째로 바뀌므로, 아래 테스트가
# "완전히 동일한 동작"을 못박는다. 특히 backtrace 동점 우선순위(diagonal > del > ins)는
# 고정 규약이다.

_ALIGN_CASES = [
    (["a", "b", "c"], ["a", "b", "c"]),
    (["a", "b", "c"], ["a", "x", "c"]),      # 치환
    (["a", "b", "c"], ["a", "c"]),           # 삭제
    (["a", "c"], ["a", "b", "c"]),           # 삽입
    (["a", "b", "c"], []),                   # 전부 삭제
    ([], ["a", "b"]),                        # 전부 삽입
    ([], []),
    (["안녕", "하세요"], ["hello", "there", "friend"]),
    (["the", "cat", "sat", "on", "the", "mat"], ["the", "cat", "sat", "in", "a", "mat", "now"]),
]


def test_align_words_hardcoded_expectations():
    """리팩터링 전 구현이 내던 값 그대로(하드코딩 기대치)여야 한다."""
    assert _align_words(["a", "b", "c"], ["a", "b", "c"]) == [0, 1, 2, 3]
    assert _align_words(["a", "b", "c"], ["a", "x", "c"]) == [0, 1, 2, 3]
    assert _align_words(["a", "b", "c"], ["a", "c"]) == [0, 2, 3]   # b 삭제 → 경계가 밀림
    assert _align_words(["a", "c"], ["a", "b", "c"]) == [0, 1, 1, 2]  # b 삽입 → 정답 위치 정체
    assert _align_words(["a", "b", "c"], []) == [3]
    assert _align_words([], ["a", "b"]) == [0, 0, 0]
    assert _align_words([], []) == [0]


def test_align_ops_reconstructs_same_hyp_to_ref():
    """_align_ops 결과에서 재구성한 hyp_to_ref가 _align_words 반환값과 동일해야 한다."""
    for ref_words, hyp_words in _ALIGN_CASES:
        rebuilt = [0] * (len(hyp_words) + 1)
        ci = cj = 0
        for op, _ri, _hj in _align_ops(ref_words, hyp_words):
            if op in ("match", "sub"):
                ci += 1
                cj += 1
            elif op == "del":
                ci += 1
            else:
                cj += 1
            rebuilt[cj] = ci
        assert rebuilt == _align_words(ref_words, hyp_words), (ref_words, hyp_words)


def test_align_ops_indices_point_at_the_right_words():
    """(op, ref_idx, hyp_idx) 인덱스가 실제 단어를 가리키는지 — del/ins의 None 규약 포함."""
    ops = _align_ops(["a", "b", "c"], ["a", "c"])
    assert ops == [("match", 0, 0), ("del", 1, None), ("match", 2, 1)]

    ops2 = _align_ops(["a", "c"], ["a", "b", "c"])
    assert [o for o, _, _ in ops2] == ["match", "ins", "match"]
    assert ops2[1] == ("ins", None, 1)


def test_align_ops_counts_match_compute_wer():
    """sub/ins/del 개수가 compute_wer의 전방 DP 집계와 일치해야 한다(동일 동점 우선순위)."""
    for ref_words, hyp_words in _ALIGN_CASES:
        if not ref_words:
            continue  # compute_wer는 정답 0단어를 조기 반환 특례로 처리한다
        ops = [o for o, _, _ in _align_ops(ref_words, hyp_words)]
        w = compute_wer(" ".join(ref_words), " ".join(hyp_words))
        assert ops.count("sub") == w["substitutions"], (ref_words, hyp_words)
        assert ops.count("ins") == w["insertions"], (ref_words, hyp_words)
        assert ops.count("del") == w["deletions"], (ref_words, hyp_words)


# ── compute_speaker_sentence_segmentation ──────────────────────────────────


def test_speaker_sentence_perfect_match():
    """2블록(2화자) x 문장 2개, 모든 경계(화자전환+블록내부)에서 hyp가 분리 → 두 F1 모두 1.0."""
    blocks = [
        {"speaker": "spk1", "sentences": ["a b c", "d e f"]},
        {"speaker": "spk2", "sentences": ["g h i", "j k l"]},
    ]
    hyp = ["a b c", "d e f", "g h i", "j k l"]
    r = compute_speaker_sentence_segmentation(blocks, hyp)
    assert r["speaker"]["f1"] == 1.0
    assert r["speaker"]["precision"] == 1.0
    assert r["speaker"]["recall"] == 1.0
    assert r["sentence"] is not None
    assert r["sentence"]["f1"] == 1.0
    assert r["sentence"]["precision"] == 1.0
    assert r["sentence"]["recall"] == 1.0


def test_speaker_sentence_missed_speaker_boundary():
    """화자전환 지점(블록1 마지막 문장 + 블록2 첫 문장)을 한 줄로 합치면 화자경계 recall이 떨어진다."""
    blocks = [
        {"speaker": "spk1", "sentences": ["a b c", "d e f"]},
        {"speaker": "spk2", "sentences": ["g h i", "j k l"]},
    ]
    hyp = ["a b c", "d e f g h i", "j k l"]
    r = compute_speaker_sentence_segmentation(blocks, hyp)
    assert r["speaker"]["recall"] < 1.0
    assert r["speaker"]["matched_boundaries"] == 0


def test_speaker_sentence_independent_metrics():
    """화자전환마다는 정확히 분리하되 블록 내부 문장은 분리 안 함 → 화자F1은 그대로 1.0, 문장 recall만 하락.

    두 지표가 서로 독립적으로 측정됨을 증명하는 핵심 케이스.
    """
    blocks = [
        {"speaker": "spk1", "sentences": ["a b c", "d e f"]},
        {"speaker": "spk2", "sentences": ["g h i"]},
    ]
    hyp = ["a b c d e f", "g h i"]
    r = compute_speaker_sentence_segmentation(blocks, hyp)
    assert r["speaker"]["f1"] == 1.0
    assert r["sentence"]["recall"] < 1.0


def test_speaker_sentence_all_single_sentence_blocks_yields_none():
    """ytn2처럼 모든 블록이 단일 문장이면 블록 내부 경계가 아예 없어 문장F1은 0.0이 아니라 None이어야 한다."""
    blocks = [
        {"speaker": "spk1", "sentences": ["a b c"]},
        {"speaker": "spk2", "sentences": ["d e f"]},
    ]
    r = compute_speaker_sentence_segmentation(blocks, ["a b c", "d e f"])
    assert r["sentence"] is None
    assert r["speaker"]["f1"] == 1.0

    # hyp가 완전히 다르게(통짜 한 줄) 나와도 여전히 not-applicable(None)이지 spurious 0.0이 아니다.
    r2 = compute_speaker_sentence_segmentation(blocks, ["a b c d e f"])
    assert r2["sentence"] is None


def test_speaker_sentence_tolerance_with_asr_error():
    """단어 삭제(d 탈락)로 경계 투영이 밀려도 tolerance=1 이내면 화자·문장 경계 모두 매칭된다."""
    blocks = [
        {"speaker": "spk1", "sentences": ["a b c", "d e f"]},
        {"speaker": "spk2", "sentences": ["g h i"]},
    ]
    hyp = ["a b c", "e f", "g h i"]  # "d" 탈락(deletion) → 경계 투영이 ±1 밀림
    r = compute_speaker_sentence_segmentation(blocks, hyp)
    assert r["speaker"]["f1"] == 1.0
    assert r["sentence"]["f1"] == 1.0


def test_speaker_sentence_boundaries_counted_per_block_transition():
    """bong1처럼 화자 id가 비인접 재등장해도 화자경계는 '블록 전환 횟수'로 세야 한다(고유 id 개수가 아님)."""
    blocks = [
        {"speaker": "spk1", "sentences": ["a b"]},
        {"speaker": "spk2", "sentences": ["c d"]},
        {"speaker": "spk1", "sentences": ["e f"]},  # spk1 비인접 재등장
        {"speaker": "spk3", "sentences": ["g h"]},
    ]
    hyp = ["a b", "c d", "e f", "g h"]
    r = compute_speaker_sentence_segmentation(blocks, hyp)
    assert r["speaker"]["ref_boundaries"] == 3  # 블록 4개 → 전환 3회 (고유 화자 3명이 아니라)
    assert r["speaker"]["matched_boundaries"] == 3
    assert r["speaker"]["recall"] == 1.0
    assert r["sentence"] is None  # 모든 블록이 단일 문장

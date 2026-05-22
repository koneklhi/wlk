"""whisperlivekit.metrics.compute_segmentation 유닛 테스트."""
from whisperlivekit.metrics import compute_segmentation


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

# -*- coding: utf-8 -*-
"""언어전환 경계 재조정(boundary reconcile) 계층 유닛 테스트 (Exp-192, 모델 불필요).

커밋 단계별로 확장된다:
- 커밋1: ASRToken.retracted 필드 + with_offset 전필드 보존.
- 커밋3: ReconcileWindow — 복원/대체/마감 3중(D1/D2/D3)/단일 컷포인트 원자성/플래그 OFF 레거시.
- 커밋4: 시간 소유권 dedup(드롭/supersede/id 승계/정상 반복 보호).
- 커밋5: 동적 keep 클램프.
"""
from whisperlivekit.timed_objects import ASRToken


# ─── 커밋1: 데이터 모델 ────────────────────────────────────────────────────────


def test_asrtoken_retracted_defaults_false():
    t = ASRToken(start=1.0, end=1.1, text="hello")
    assert t.retracted is False


def test_with_offset_preserves_all_fields():
    """with_offset은 start/end만 이동하고 나머지 전 필드를 보존해야 한다.

    dataclasses.replace 기반이라 이후 필드가 추가돼도 복사 누락이 생기지 않는다 —
    과거 위치 인자 나열 방식은 새 필드(retracted 등)를 조용히 잃는 footgun이었다.
    """
    t = ASRToken(
        start=10.0, end=10.5, text=" 미니스터", speaker=3,
        detected_language="ko", probability=0.87, retracted=True,
    )
    moved = t.with_offset(2.5)
    assert moved is not t
    assert moved.start == 12.5
    assert moved.end == 13.0
    assert moved.text == " 미니스터"
    assert moved.speaker == 3
    assert moved.detected_language == "ko"
    assert moved.probability == 0.87
    assert moved.retracted is True
    # 원본 불변
    assert t.start == 10.0 and t.end == 10.5


def test_with_offset_copies_every_declared_field():
    """필드 목록이 늘어나도 with_offset이 전부 복사하는지 구조적으로 고정한다."""
    import dataclasses
    t = ASRToken(start=0.0, end=0.1, text="x")
    moved = t.with_offset(1.0)
    for f in dataclasses.fields(ASRToken):
        if f.name in ("start", "end"):
            continue
        assert getattr(moved, f.name) == getattr(t, f.name), f.name

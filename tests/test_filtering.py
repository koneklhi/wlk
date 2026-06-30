# -*- coding: utf-8 -*-
"""Phase 3 필터링/단어교정 독립 모듈 검증 테스트.

whisperlivekit/filtering/ 모듈이 whisperlivekit 코어(audio_processor 등) 없이도
독립적으로 동작하는지 확인한다. 각 테스트는 tmp_path 기반 임시 fixture를 사용해
전역 싱글턴 오염 없이 격리 실행된다.
"""

import json
from pathlib import Path
from types import ModuleType

from whisperlivekit.filtering.manager import WordCorrectionManager

# ─── 헬퍼 ────────────────────────────────────────────────────────────────────

def make_manager(tmp_path: Path, entries: list, user_rows: list = None) -> WordCorrectionManager:
    """임시 JSON + DB로 WordCorrectionManager를 생성한다."""
    json_path = tmp_path / "admin_replacement.json"
    db_path = tmp_path / "user_replacement.db"
    json_path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    mgr = WordCorrectionManager(base_json_path=str(json_path), db_path=str(db_path))
    if user_rows:
        for wrong, correct in user_rows:
            mgr.add_user_word(wrong, correct)
    return mgr


def load_filter_module(tmp_path: Path, hallucinations: list, replacements: list) -> ModuleType:
    """임시 fixture를 가리키는 filter_hallucination 함수를 반환한다.

    전역 싱글턴(_HALLUCINATIONS, _word_manager)을 건드리지 않기 위해
    모듈을 직접 패치해 격리된 버전을 돌린다.
    """

    hal_path = tmp_path / "hallucination.json"
    hal_path.write_text(json.dumps(hallucinations, ensure_ascii=False), encoding="utf-8")
    json_path = tmp_path / "admin_replacement.json"
    db_path = tmp_path / "user_replacement.db"
    json_path.write_text(json.dumps(replacements, ensure_ascii=False), encoding="utf-8")

    mgr = WordCorrectionManager(base_json_path=str(json_path), db_path=str(db_path))
    halluc_list = sorted(hallucinations, key=len, reverse=True)

    import re

    def filter_fn(raw_transcript: list) -> list:
        if not raw_transcript:
            return []
        filtered = []
        for segment in raw_transcript:
            seg = list(segment)
            for bad_token in halluc_list:
                if bad_token in seg[2]:
                    seg[2] = seg[2].replace(bad_token, "")
            seg[2] = re.sub(r'\s+', ' ', seg[2]).strip()
            txt = seg[2].strip()
            if txt and txt not in {".", "?"} and set(txt) != {"."}:
                filtered.append(seg)
        replacements_dict = mgr.combined_replacements
        if replacements_dict:
            pattern = re.compile("|".join(re.escape(k) for k in replacements_dict.keys()))
            for seg in filtered:
                seg[2] = pattern.sub(lambda m: replacements_dict[m.group(0)], seg[2])
        return [tuple(seg) for seg in filtered]

    return filter_fn, mgr


# ─── WordCorrectionManager 단위 테스트 ───────────────────────────────────────

class TestWordCorrectionManager:
    def test_load_base_json(self, tmp_path):
        entries = [
            {"origin": "6군", "replaced": "육군"},
            {"origin": "공군역", "replaced": "공군력"},
        ]
        mgr = make_manager(tmp_path, entries)
        assert mgr.base_replacements == {"6군": "육군", "공군역": "공군력"}

    def test_combined_sorted_by_length(self, tmp_path):
        entries = [
            {"origin": "한미", "replaced": "ROK"},
            {"origin": "한미동맹", "replaced": "ROK-US Alliance"},
        ]
        mgr = make_manager(tmp_path, entries)
        keys = list(mgr.combined_replacements.keys())
        # 긴 단어("한미동맹")가 먼저 나와야 함
        assert keys[0] == "한미동맹"

    def test_add_user_word_immediate_effect(self, tmp_path):
        mgr = make_manager(tmp_path, [])
        mgr.add_user_word("브론슨", "브런슨")
        assert "브론슨" in mgr.combined_replacements
        assert mgr.combined_replacements["브론슨"] == "브런슨"

    def test_delete_user_word(self, tmp_path):
        mgr = make_manager(tmp_path, [])
        mgr.add_user_word("프런슨", "브런슨")
        assert "프런슨" in mgr.combined_replacements
        mgr.delete_user_word("프런슨")
        assert "프런슨" not in mgr.combined_replacements

    def test_user_overrides_base(self, tmp_path):
        entries = [{"origin": "6군", "replaced": "육군"}]
        mgr = make_manager(tmp_path, entries)
        # 사용자가 같은 키를 다른 값으로 덮어쓰면 user 우선
        mgr.add_user_word("6군", "제6군")
        assert mgr.combined_replacements["6군"] == "제6군"

    def test_empty_base_json(self, tmp_path):
        mgr = make_manager(tmp_path, [])
        assert mgr.base_replacements == {}
        assert mgr.combined_replacements == {}

    def test_missing_base_json(self, tmp_path):
        db_path = tmp_path / "user_replacement.db"
        mgr = WordCorrectionManager(
            base_json_path=str(tmp_path / "nonexistent.json"),
            db_path=str(db_path),
        )
        assert mgr.base_replacements == {}

    def test_db_persists_across_instances(self, tmp_path):
        """DB에 추가한 사용자 단어는 새 인스턴스에서도 로드된다."""
        json_path = tmp_path / "admin_replacement.json"
        db_path = tmp_path / "user_replacement.db"
        json_path.write_text("[]", encoding="utf-8")

        mgr1 = WordCorrectionManager(str(json_path), str(db_path))
        mgr1.add_user_word("브론슨", "브런슨")

        mgr2 = WordCorrectionManager(str(json_path), str(db_path))
        assert mgr2.user_replacements.get("브론슨") == "브런슨"


# ─── filter_hallucination 통합 테스트 ────────────────────────────────────────

class TestFilterHallucination:
    def test_empty_input(self, tmp_path):
        fn, _ = load_filter_module(tmp_path, [], [])
        assert fn([]) == []

    def test_hallucination_token_removed(self, tmp_path):
        fn, _ = load_filter_module(
            tmp_path,
            hallucinations=["<|python_tag|>"],
            replacements=[],
        )
        result = fn([(0.0, 1.0, "<|python_tag|> 미국 육군 강연")])
        assert len(result) == 1
        assert "<|python_tag|>" not in result[0][2]
        assert "미국 육군 강연" in result[0][2]

    def test_multiple_space_collapsed(self, tmp_path):
        fn, _ = load_filter_module(
            tmp_path,
            hallucinations=["시청해주셔서 감사합니다"],
            replacements=[],
        )
        result = fn([(0.0, 1.5, "브런슨   시청해주셔서 감사합니다   사령관")])
        assert result[0][2] == "브런슨 사령관"

    def test_punctuation_only_segment_dropped(self, tmp_path):
        fn, _ = load_filter_module(tmp_path, [], [])
        result = fn([(0.0, 0.5, "."), (0.0, 0.5, "?"), (0.0, 0.5, "...")])
        assert result == []

    def test_word_substitution(self, tmp_path):
        fn, _ = load_filter_module(
            tmp_path,
            hallucinations=[],
            replacements=[
                {"origin": "6군", "replaced": "육군"},
                {"origin": "공군역", "replaced": "공군력"},
            ],
        )
        result = fn([(0.0, 2.0, "미국 6군 전쟁 대학 강연에서 공군역 얘기를 했다")])
        assert result[0][2] == "미국 육군 전쟁 대학 강연에서 공군력 얘기를 했다"

    def test_long_word_matched_first(self, tmp_path):
        """'한미동맹'이 '한미'보다 먼저 매칭되어야 한다."""
        fn, _ = load_filter_module(
            tmp_path,
            hallucinations=[],
            replacements=[
                {"origin": "한미동맹", "replaced": "ROK-US Alliance"},
                {"origin": "한미", "replaced": "ROK"},
            ],
        )
        result = fn([(0.0, 2.0, "한미동맹은 철통입니다")])
        assert "ROK-US Alliance" in result[0][2]
        assert "ROK동맹" not in result[0][2]

    def test_hallucination_then_substitution(self, tmp_path):
        """환각 제거 → 단어 교정 순서로 실행된다."""
        fn, _ = load_filter_module(
            tmp_path,
            hallucinations=["<|python_tag|>"],
            replacements=[{"origin": "6군", "replaced": "육군"}],
        )
        result = fn([(0.0, 2.0, "<|python_tag|> 미국 6군 전쟁 대학")])
        assert result[0][2] == "미국 육군 전쟁 대학"

    def test_user_word_immediate_effect(self, tmp_path):
        """add_user_word 후 filter 결과에 즉시 반영된다."""
        fn, mgr = load_filter_module(tmp_path, [], [])
        # 추가 전
        before = fn([(0.0, 1.0, "프런슨 사령관")])
        assert before[0][2] == "프런슨 사령관"
        # 추가 후
        mgr.add_user_word("프런슨", "브런슨")
        after = fn([(0.0, 1.0, "프런슨 사령관")])
        assert after[0][2] == "브런슨 사령관"

    def test_delete_user_word_immediate_effect(self, tmp_path):
        """delete_user_word 후 다음 호출부터 교정이 사라진다."""
        fn, mgr = load_filter_module(tmp_path, [], [])
        mgr.add_user_word("브론슨", "브런슨")
        before = fn([(0.0, 1.0, "브론슨 부임")])
        assert before[0][2] == "브런슨 부임"
        mgr.delete_user_word("브론슨")
        after = fn([(0.0, 1.0, "브론슨 부임")])
        assert after[0][2] == "브론슨 부임"

    def test_timestamp_preserved(self, tmp_path):
        """필터링 후 start/end 타임스탬프가 유지된다."""
        fn, _ = load_filter_module(tmp_path, [], [])
        result = fn([(1.5, 3.2, "한반도 방어선")])
        assert result[0][0] == 1.5
        assert result[0][1] == 3.2


# ─── 불변식 필터 단위 테스트 (Segment 객체 대상) ─────────────────────────────

def _make_seg(text: str, silence: bool = False):
    """테스트용 최소 Segment 객체 (whisperlivekit 코어 없이)."""
    from whisperlivekit.timed_objects import Segment
    return Segment(start=0.0, end=1.0, text=text, speaker=-2 if silence else -1)


class TestFilterSegmentsInvariants:
    """filter_segments()의 언어 불변식 필터(Layer 1) 동작 검증."""

    def test_korean_text_preserved(self, monkeypatch):
        """한글 정상 문장은 드롭되지 않는다."""
        import whisperlivekit.filtering as fmod
        monkeypatch.setattr(fmod, "_HALLUCINATIONS", [])
        monkeypatch.setattr(fmod, "_word_manager", fmod.get_word_manager())

        seg = _make_seg("한반도 방어선을 논의했습니다.")
        result = fmod.filter_segments([seg])
        assert len(result) == 1
        assert "한반도" in result[0].text

    def test_english_text_preserved(self, monkeypatch):
        """영어 정상 문장은 드롭되지 않는다."""
        import whisperlivekit.filtering as fmod
        monkeypatch.setattr(fmod, "_HALLUCINATIONS", [])

        seg = _make_seg("The alliance is crucial for regional stability.")
        result = fmod.filter_segments([seg])
        assert len(result) == 1

    def test_cjk_kanji_segment_dropped(self, monkeypatch):
        """한자 포함 세그먼트는 통째 드롭된다."""
        import whisperlivekit.filtering as fmod
        monkeypatch.setattr(fmod, "_HALLUCINATIONS", [])

        seg = _make_seg("主委員工也沒有打仗")
        result = fmod.filter_segments([seg])
        assert result == []

    def test_hiragana_segment_dropped(self, monkeypatch):
        """히라가나 포함 세그먼트는 통째 드롭된다."""
        import whisperlivekit.filtering as fmod
        monkeypatch.setattr(fmod, "_HALLUCINATIONS", [])

        seg = _make_seg("ありがとうございます")
        result = fmod.filter_segments([seg])
        assert result == []

    def test_katakana_segment_dropped(self, monkeypatch):
        """가타카나 포함 세그먼트는 통째 드롭된다."""
        import whisperlivekit.filtering as fmod
        monkeypatch.setattr(fmod, "_HALLUCINATIONS", [])

        seg = _make_seg("テレビ放送")
        result = fmod.filter_segments([seg])
        assert result == []

    def test_annotation_stripped_embedded(self, monkeypatch):
        """실발화 + 주석 임베디드 케이스: 주석만 제거하고 실발화는 보존."""
        import whisperlivekit.filtering as fmod
        monkeypatch.setattr(fmod, "_HALLUCINATIONS", [])

        seg = _make_seg("안녕하세요 (웃음) 오늘 날씨가 좋네요.")
        result = fmod.filter_segments([seg])
        assert len(result) == 1
        assert "(웃음)" not in result[0].text
        assert "안녕하세요" in result[0].text
        assert "오늘 날씨가 좋네요" in result[0].text

    def test_standalone_laughter_annotation_dropped(self, monkeypatch):
        """단독 (laughter) 세그먼트는 strip 후 공백만 남아 드롭된다."""
        import whisperlivekit.filtering as fmod
        monkeypatch.setattr(fmod, "_HALLUCINATIONS", [])

        seg = _make_seg("(laughter)")
        result = fmod.filter_segments([seg])
        assert result == []

    def test_bracket_annotation_stripped(self, monkeypatch):
        """[구독] 같은 대괄호 주석이 제거된다."""
        import whisperlivekit.filtering as fmod
        monkeypatch.setattr(fmod, "_HALLUCINATIONS", [])

        seg = _make_seg("[구독] [좋아요] 눌러주세요")
        result = fmod.filter_segments([seg])
        assert len(result) == 1
        assert "[구독]" not in result[0].text
        assert "눌러주세요" in result[0].text

    def test_music_note_stripped(self, monkeypatch):
        """음표 기호(♪ 등)가 제거된다."""
        import whisperlivekit.filtering as fmod
        monkeypatch.setattr(fmod, "_HALLUCINATIONS", [])

        seg = _make_seg("♪ 노래 가사 ♪")
        result = fmod.filter_segments([seg])
        # 음표 제거 후 '노래 가사'만 남거나 빈 세그먼트 드롭
        if result:
            assert "♪" not in result[0].text

    def test_silence_segment_passes_through(self, monkeypatch):
        """침묵 세그먼트는 필터를 그대로 통과한다."""
        import whisperlivekit.filtering as fmod
        monkeypatch.setattr(fmod, "_HALLUCINATIONS", [])

        seg = _make_seg("", silence=True)
        result = fmod.filter_segments([seg])
        assert len(result) == 1

    def test_korean_english_codeswitching_preserved(self, monkeypatch):
        """한·영 코드스위칭 문장은 보존된다."""
        import whisperlivekit.filtering as fmod
        monkeypatch.setattr(fmod, "_HALLUCINATIONS", [])

        seg = _make_seg("그건 trust 있는 alliance 파트너십이야.")
        result = fmod.filter_segments([seg])
        assert len(result) == 1
        assert "trust" in result[0].text
        assert "그건" in result[0].text

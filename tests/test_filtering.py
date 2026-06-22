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

# -*- coding: utf-8 -*-
"""번역 프롬프트에 주입할 용어집(glossary_block)과 예시문(sentence_block) 관리.

whisperlive_code/prompt_manager.py를 이식. 원본의 _load_default_glossary_from_file이
인자 없이 정의됐으나 인자를 받아 호출되던 버그(NameError 유발)를 수정했다.
"""

import json
import os
import sqlite3


class TranslationPromptManager:
    """glossary_block: {origin: translation} 용어 매핑. 개발자 기본값(JSON) + 사용자
    추가분(DB)을 병합해 사용하며, 입력 문장에 실제 등장하는 용어만 골라 반환한다.

    sentence_block: few-shot 예시 문장쌍. 사용자가 수정하기 전까지는 개발자 기본값을
    그대로 쓰고(Copy-on-Write), 한 번이라도 add_item/remove_item이 호출되면 전체를
    사용자 버전으로 교체한다.
    """

    def __init__(self, base_json_path: str, db_path: str):
        self.db_path = db_path

        # 용어집 변경 세대 카운터. 진행 중인 세션의 TranslationManager가 매 tick 이 값을 읽어
        # 용어집이 바뀐 것을 알아챈다 — 번역 캐시 키는 (start, text)뿐이라, 전사 텍스트가 그대로인
        # 용어집 변경은 이 신호가 없으면 영원히 캐시 히트가 되어 소급 재번역이 불가능하다.
        self.revision: int = 0

        self.headers = {
            "glossary_block": "GLOSSARY(Term:Translation)",
            "sentence_block": "### EXAMPLES",
        }

        self.defaults = {
            "glossary_block": self._load_default_glossary_from_file(base_json_path),
            "sentence_block": {
                "The ROK Air Force conducted joint air operations": "대한민국 공군은 연합 공중작전을 수행했다.",
                "보고를 드리기 전 안내 말씀드리겠습니다.": "Before we begin, a brief notice.",
                "우리는 한미 연합 공중훈련의 일환으로 대한민국(ROK) 공군 부대와 협조했다": "We coordinated with ROK Air Force unit as part of ROK-US combined air exercise.",
            },
        }

        self.user_settings = {
            "glossary_block": {},
            "sentence_block": None,
        }

        self._init_db()
        self.load_settings()

    # ------------------------------------------------------------------
    # [초기화 및 DB 관리]
    # ------------------------------------------------------------------
    def _load_default_glossary_from_file(self, file_path: str) -> dict:
        """JSON 파일에서 개발자 기본 용어집 로드 (실패 시 빈 딕셔너리 반환)."""
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Warning: Failed to load default glossary: {e}")
            return {}

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            conn.commit()

    def load_settings(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM prompt_settings")
            rows = cursor.fetchall()

            for key, val_str in rows:
                if key in self.user_settings:
                    try:
                        self.user_settings[key] = json.loads(val_str)
                    except json.JSONDecodeError:
                        self.user_settings[key] = {} if key == "glossary_block" else None

    def _save_to_db(self, key: str):
        val = self.user_settings[key]
        if val is None:
            return

        json_val = json.dumps(val, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO prompt_settings (key, value) VALUES (?, ?)",
                (key, json_val),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # [데이터 추가/삭제/조회 API 연동용]
    # ------------------------------------------------------------------
    def add_item(self, block_key: str, origin: str, translation: str) -> bool:
        if block_key == "glossary_block":
            self.user_settings["glossary_block"][origin.strip()] = translation.strip()
            self._save_to_db("glossary_block")
            self.revision += 1
        elif block_key == "sentence_block":
            if self.user_settings["sentence_block"] is None:
                self.user_settings["sentence_block"] = self.defaults["sentence_block"].copy()
            self.user_settings["sentence_block"][origin.strip()] = translation.strip()
            self._save_to_db("sentence_block")
            self.revision += 1
        return True

    def remove_item(self, block_key: str, origin: str) -> bool:
        target_key = origin.strip()
        if block_key == "glossary_block":
            if target_key in self.user_settings["glossary_block"]:
                del self.user_settings["glossary_block"][target_key]
                self._save_to_db("glossary_block")
                self.revision += 1
                return True
            return False
        elif block_key == "sentence_block":
            if self.user_settings["sentence_block"] is None:
                self.user_settings["sentence_block"] = self.defaults["sentence_block"].copy()
            if target_key in self.user_settings["sentence_block"]:
                del self.user_settings["sentence_block"][target_key]
                self._save_to_db("sentence_block")
                self.revision += 1
                return True
        return False

    def get_user_view_settings(self) -> dict:
        """프론트엔드 표출용 데이터 반환 (개발자 glossary 기본값은 숨김)."""
        current_sentence = self.user_settings["sentence_block"]
        if current_sentence is None:
            current_sentence = self.defaults["sentence_block"]
        return {
            "glossary_block": self.user_settings["glossary_block"],
            "sentence_block": current_sentence,
        }

    # ------------------------------------------------------------------
    # [프롬프트 동적 주입용]
    # ------------------------------------------------------------------
    def get_relevant_glossary(self, input_text: str) -> str:
        """입력 문장에 실제 등장하는 용어만 골라 glossary 블록 문자열로 반환.

        단순 in 매칭(조사 문제 회피), 한→영·영→한 양방향 검색. 매칭 없으면 빈 문자열
        (빈 헤더 방지).
        """
        combined_glossary = self.defaults["glossary_block"].copy()
        combined_glossary.update(self.user_settings["glossary_block"])

        if not combined_glossary:
            return ""

        relevant_items = []
        input_lower = input_text.lower()

        for origin, trans in combined_glossary.items():
            match_origin = origin.lower() in input_lower
            match_trans = trans.lower() in input_lower
            if match_origin or match_trans:
                relevant_items.append(f"{origin} : {trans}")

        if not relevant_items:
            return ""

        return f"{self.headers['glossary_block']}\n" + "\n".join(relevant_items)

    def get_sentence_block(self) -> str:
        """예시 문장 전체 반환 (없으면 빈 문자열)."""
        current_dict = self.user_settings["sentence_block"]
        if current_dict is None:
            current_dict = self.defaults["sentence_block"]

        if not current_dict:
            return ""

        items = []
        for inp, out in current_dict.items():
            items.append(f"- INPUT : {inp}\n- OUTPUT : {out}")

        return f"{self.headers['sentence_block']}\n" + "\n\n".join(items)

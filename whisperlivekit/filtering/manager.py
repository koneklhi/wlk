# -*- coding: utf-8 -*-
import json
import os
import sqlite3


class WordCorrectionManager:
    """
    base_replacements : JSON 파일로부터 로드된 기본 단어장
    user_replacements : DB에서 로드된 사용자 단어장
    combined_replacements : 병합 및 긴 단어 순 정렬된 결과
    """
    def __init__(self, base_json_path, db_path):
        self.db_path = db_path

        self.base_json_path = base_json_path
        self.base_replacements = self._load_base_from_json()

        self.user_replacements = {}
        self.combined_replacements = {}

        self._init_db()
        self.refresh_replacements()

    def _load_base_from_json(self) -> dict:
        replacements = {}
        if not os.path.isfile(self.base_json_path):
            print(f"JSON 파일이 존재하지 않습니다: {self.base_json_path}")
            return replacements

        try:
            with open(self.base_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[Error] Json parsing failed: {e}")
            return replacements
        if not isinstance(data, list):
            print("[Warning] JSON root element should be a list")
            return replacements

        for entry in data:
            if not isinstance(entry, dict):
                print("[Warning] eACH ITEM IN json MUST BE an object")
                continue
            origin = entry.get("origin")
            replaced = entry.get("replaced")
            if origin is None or replaced is None:
                print(
                    "[Warning] Every object must contain origin and replaced keys."
                )
                continue
            replacements[origin] = replaced
        return replacements

    def _init_db(self):
        """사용자 정의 단어장 SQLite DB 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wrong_word TEXT UNIQUE NOT NULL,
                    correct_word TEXT NOT NULL
                )
            ''')
            conn.commit()

    def refresh_replacements(self):
        """DB 로드 -> 병합 -> 긴 단어 우선 정렬 실행"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT wrong_word, correct_word FROM user_corrections")
            rows = cursor.fetchall()
            self.user_replacements = {w: c for w, c in rows}

        # 병합 (사용자 단어가 기본 단어보다 우선순위 높음)
        merged = {**self.base_replacements, **self.user_replacements}

        # 긴 단어부터 대치하도록 정렬
        sorted_keys = sorted(merged.keys(), key=len, reverse=True)
        self.combined_replacements = {k: merged[k] for k in sorted_keys}

        print(f"[Filtering] 단어장 갱신 완료 (총 {len(self.combined_replacements)}개)")

    def add_user_word(self, wrong, correct):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO user_corrections (wrong_word, correct_word) VALUES (?, ?)",
                (wrong, correct)
            )
            conn.commit()
        self.refresh_replacements()

    def delete_user_word(self, wrong):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_corrections WHERE wrong_word = ?", (wrong,))
            conn.commit()
        self.refresh_replacements()

    def is_user_defined(self, wrong: str) -> bool:
        """`wrong`이 사용자 DB(user_corrections)에 존재하는지 여부."""
        return wrong in self.user_replacements

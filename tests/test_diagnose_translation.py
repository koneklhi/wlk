"""scripts/diagnose_translation.py 유닛 테스트 (네트워크 없음 - HTTP 응답은 스텁).

핵심은 test_stages_match_real_backend 다. 진단 스크립트의 stages()는 실제 백엔드의 후처리를
'재현'하는 코드라 원본이 바뀌면 조용히 어긋날 수 있다 — 그래서 실제 구현
(_call_completions / _call_chat)을 스텁 응답으로 직접 돌려 마지막 단계 값이 같은지 대조한다.

겸사겸사 이 테스트는 "응답이 '<' 로 시작하면 통째로 빈 문자열이 된다"는 현재 동작을 문서화한다
(배포 PC 번역 누락의 유력 후보).
"""

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from diagnose_translation import stages  # noqa: E402

from whisperlivekit.llm_translation.translator import LlamaTranslator, OllamaTranslator  # noqa: E402

# (설명, LLM 원본 응답)
_RAW_CASES = [
    ("정상 응답 + 종료 태그", "4월 주요 일정을 표시합니다.<|end|>"),
    ("응답이 '<' 로 시작", "<|channel|>final<|message|>4월 주요 일정을 표시합니다."),
    ("개행뿐인 응답", "\n\n"),
    ("빈 응답", ""),
    ("따옴표로 감싼 응답", '"4월 주요 일정을 표시합니다."'),
    ("여러 줄 폭주", "첫 문장입니다.\n두 번째 문장입니다.\n세 번째입니다."),
]


class _StubResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _StubClient:
    """translator.client 자리에 꽂는 최소 스텁. 실제 네트워크를 타지 않는다."""

    def __init__(self, payload):
        self._payload = payload
        self.is_closed = True

    async def post(self, *args, **kwargs):
        return _StubResponse(self._payload)


def _llama(raw):
    translator = LlamaTranslator("stub-model", "http://stub")
    translator.client = _StubClient({"choices": [{"text": raw}]})
    return translator


def _ollama(raw):
    translator = OllamaTranslator("stub-model", "http://stub")
    translator.client = _StubClient({"choices": [{"message": {"content": raw}}]})
    return translator


@pytest.mark.parametrize("label,raw", _RAW_CASES, ids=[c[0] for c in _RAW_CASES])
@pytest.mark.anyio
async def test_stages_match_real_backend(label, raw):
    """stages()의 마지막 단계 = 실제 백엔드 반환값 (llama/ollama 양쪽)."""
    llama = _llama(raw)
    assert stages(raw, "llama", llama._sanitize_result)[-1][1] == await llama._call_completions("prompt")

    ollama = _ollama(raw)
    assert stages(raw, "ollama", ollama._sanitize_result)[-1][1] == await ollama._call_chat("sys", "content")


@pytest.mark.anyio
async def test_leading_angle_bracket_empties_result_on_llama():
    """현재 동작 문서화 — '<' 로 시작하는 응답은 llama 경로에서 통째로 빈 문자열이 된다."""
    raw = "<|channel|>final<|message|>4월 주요 일정을 표시합니다."

    assert await _llama(raw)._call_completions("prompt") == ""
    # 같은 응답이라도 ollama 경로에는 '<' 절단이 없어 내용이 살아남는다(배포 PC에서만 재현되는 이유).
    assert await _ollama(raw)._call_chat("sys", "content") != ""


def test_stages_reports_the_emptying_step():
    """진단 출력이 '어느 단계에서 비었는지' 짚어줄 수 있어야 한다."""
    raw = "<|channel|>final<|message|>내용"
    steps = stages(raw, "llama", _llama(raw)._sanitize_result)

    labels = [label for label, _ in steps]
    assert labels[0].startswith("(1)")
    first_empty = next(label for label, value in steps if not value.strip())
    assert first_empty.startswith("(2)"), "'<' 절단 단계에서 비었다고 짚어야 한다"

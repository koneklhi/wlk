r"""번역 결과가 빈 문자열이 되는 지점을 찾는 일회성 진단 스크립트 (읽기 전용).

배경: 배포 PC에서 특정 문장이 전사만 되고 번역이 나오지 않으며, 관리자 페이지 재번역도
"번역 결과를 얻지 못했습니다"만 반복하는 사례가 보고됐다. 이 메시지는 basic_server.py의
``/api/retranslate``가 **예외 없이 빈 문자열을 받았을 때만** 낸다 — 즉 타임아웃(504)·연결
실패(502)·기타 예외(500)가 아니다. LLM은 200으로 응답했고 그 응답이 우리 후처리에서
빈 문자열이 된 것이다.

``LlamaTranslator._call_completions``에서 무예외로 빈 문자열이 되는 경로는 셋뿐이다:

    text = data["choices"][0]["text"]
    if "<" in text:
        text = text[: text.find("<")]     # (1) 응답이 '<' 로 시작하면 통째로 "" 가 된다
    text = text.strip().strip('"').strip("'")
    text = self._sanitize_result(text)     # (2) 개행뿐인 응답이면 "" 가 된다
    return text                            # (3) 애초에 빈 응답

셋 다 로그를 남기지 않아 서버 로그만으로는 구분할 수 없다. 그래서 이 스크립트는 **프로덕션과
똑같은 요청**(용어집·RAG 블록 포함)을 보내고 ``client.post``를 감싸 **후처리 이전의 원본 응답**을
찍은 뒤, 위 단계를 하나씩 적용해 **어디서 비는지** 보여준다. 요청 조립은 프로젝트 코드
(``create_translator``·``build_system_blocks``·``build_prompt``)를 그대로 재사용하므로 실서버와
프롬프트가 어긋나지 않는다.

서버 코드에 계측을 심고 재반입·재기동하는 것보다 빠르고, 서버 동작을 바꾸지 않는다.

주의: ``<`` 절단은 **llama 백엔드에만** 있다(OllamaTranslator._call_chat에는 없다). 따라서 개발 PC의
Ollama로는 이 현상을 재현할 수 없다 — 배포 PC(llama)에서 실행해야 한다.

사용법 (배포 PC, 저장소 루트에서):
    C:\Python312\python.exe scripts\diagnose_translation.py
    C:\Python312\python.exe scripts\diagnose_translation.py --text "번역 안 되는 문장" --show-prompt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whisperlivekit.llm_translation.translator import create_translator  # noqa: E402

#: 배포 PC에서 실제로 실패가 보고된 문장 — 인자 없이 돌리면 이것부터 재현한다.
DEFAULT_TEXT = "Sir, April key schedule is displayed."
DEFAULT_TIMEOUT_S = 60.0

logger = logging.getLogger(__name__)


def stages(raw: str, serve: str, sanitize) -> list:
    """``_call_completions``/``_call_chat``의 후처리를 단계별로 재현한다.

    반환값의 마지막 단계 값은 실제 백엔드 메서드의 반환값과 **같아야 한다** —
    이 동치성은 tests/test_diagnose_translation.py가 실제 구현을 돌려 검증한다.
    """
    steps = [("(1) 원본 응답", raw)]
    text = raw
    if serve == "llama":
        if "<" in text:
            text = text[: text.find("<")]
            steps.append(("(2) '<' 이후 절단", text))
        else:
            steps.append(("(2) '<' 없음 - 절단 안 함", text))
        text = text.strip().strip('"').strip("'")
        steps.append(("(3) strip", text))
    else:
        text = text.strip()
        steps.append(("(3) strip", text))
    text = sanitize(text)
    steps.append(("(4) _sanitize_result", text))
    return steps


def _extract_raw(payload: dict, serve: str) -> str:
    choice = payload["choices"][0]
    return choice["text"] if serve == "llama" else choice["message"]["content"]


async def diagnose(args) -> int:
    translator = create_translator(serve=args.serve, model_name=args.model, endpoint=args.endpoint)

    captured = []
    original_post = translator.client.post

    async def spy_post(*post_args, **post_kwargs):
        response = await original_post(*post_args, **post_kwargs)
        captured.append(response)
        return response

    translator.client.post = spy_post

    resolved = translator.resolve_src_lang(args.text, args.src_lang)
    to_lang = translator.get_to_lang(resolved)
    print(f"[진단] 입력      = {args.text!r}")
    print(f"[진단] src_lang  = {args.src_lang} -> 보정 후 {resolved}  (번역 방향 {resolved} -> {to_lang})")
    print(f"[진단] 백엔드    = serve={args.serve} model={args.model} endpoint={args.endpoint}")
    print(f"[진단] use_rag   = {not args.no_rag}")

    try:
        result = await asyncio.wait_for(
            translator.translate_sentence(args.text, args.src_lang, use_rag=not args.no_rag),
            timeout=args.timeout,
        )
    except asyncio.TimeoutError:
        print(f"\n[진단] {args.timeout:.0f}초 내 응답 없음 - LLM 서버가 응답하지 않는다(원인 B 아님).")
        return 2
    finally:
        translator.client.post = original_post
        await translator.close()

    if not captured:
        print("\n[진단] HTTP 요청이 한 번도 나가지 않았다 - 요청 조립 단계에서 실패했다.")
        return 2

    for index, response in enumerate(captured, start=1):
        print(f"\n{'=' * 70}\nLLM 호출 #{index}  (HTTP {response.status_code})\n{'=' * 70}")
        if args.show_prompt:
            body = json.loads(response.request.content.decode("utf-8"))
            print("--- 보낸 프롬프트 ---")
            print(body.get("prompt") or json.dumps(body.get("messages"), ensure_ascii=False, indent=2))
            print("--- 프롬프트 끝 ---")
        try:
            raw = _extract_raw(response.json(), args.serve)
        except (KeyError, IndexError, ValueError) as exc:
            print(f"응답 형식이 예상과 다르다({exc}) - 원문: {response.text[:500]!r}")
            continue

        emptied_at = None
        for label, value in stages(raw, args.serve, translator._sanitize_result):
            print(f"  {label:<28} {value[:300]!r}")
            if emptied_at is None and not value.strip():
                emptied_at = label
        if emptied_at:
            print(f"  >>> 이 호출은 '{emptied_at}' 단계에서 비었다.")

    print(f"\n{'=' * 70}")
    print(f"최종 translate_sentence 반환값 = {result[:300]!r}")
    if result:
        print("판정: 이번 실행에서는 번역이 정상으로 나왔다 - 원인 B가 재현되지 않았다.")
        return 0
    print(
        "판정: 빈 문자열이다. 위 단계 출력에서 어느 단계가 값을 비웠는지 확인하라.\n"
        "      (1)에서 이미 비었으면 LLM이 빈 응답을 준 것이고,\n"
        "      (2)에서 비었으면 응답이 '<' 로 시작해 절단 규칙에 통째로 잘린 것이다(유력 후보).\n"
        "      이 출력을 그대로 회신하면 수정 방향을 정할 수 있다."
    )
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="번역 결과가 빈 문자열이 되는 단계를 찾는다(읽기 전용, 서버 동작 무변경).",
    )
    parser.add_argument("--text", default=DEFAULT_TEXT, help="진단할 문장")
    parser.add_argument("--src-lang", default="ko", help="STT가 붙인 언어(문자 구성으로 자동 보정된다)")
    parser.add_argument("--serve", default="llama", choices=["llama", "ollama"])
    parser.add_argument("--model", default="gpt-oss-20b")
    parser.add_argument("--endpoint", default="http://localhost:2010")
    parser.add_argument("--no-rag", action="store_true", help="RAG 블록 없이 요청(확정 경로는 RAG를 쓴다)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--show-prompt", action="store_true", help="실제로 보낸 프롬프트 전문 출력")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, OSError):
        pass
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    return asyncio.run(diagnose(args))


if __name__ == "__main__":
    sys.exit(main())

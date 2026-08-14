#!/usr/bin/env python3
"""VBCable 브라우저 자동화 전사 테스트.

기본 측정 대상은 **배포 UI**(React, `frontend/app/` → `frontend/static/`, base `/wlkies`)다.
내장 UI(`whisperlivekit/web/`)는 `--ui inline`(= `GET /dev`)으로 계속 몰 수 있다 — A/B 비교와
회귀 디버깅용으로만 남긴다.

전제 조건:
  - Windows 소리 설정에서 VBCable이 기본 입출력으로 설정됨
  - WhisperLiveKit 서버가 실행 중
  - 배포 UI dist(`frontend/static/index.html`)가 존재하고 소스보다 최신 (`cd frontend/app && pnpm build`)
  - playwright install chromium 실행 완료

사용법:
    python scripts/vbcable_test.py test_data/sbs1.mp3
    python scripts/vbcable_test.py test_data/sbs1.mp3 --ui inline
    python scripts/vbcable_test.py test_data/sbs1.mp3 --wait 30 --json
    python scripts/vbcable_test.py test_data/sbs1.mp3 --output-device "CABLE Input"
"""

import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

SAMPLE_RATE = 16000

#: 배포 UI 전사 화면 경로. `GET /`는 여기로 302 리다이렉트된다(basic_server._frontend_base).
DEPLOY_PATH = "/wlkies/"

#: 배포 UI 자동화 계약 — `frontend/app/src/components/*.tsx`의 `data-testid`와 짝이다.
#: 프런트에서 이 속성을 지우거나 개명하면 측정이 조용히 깨진다(frontend/app/README.md 자동화 계약 절).
SEL_TOGGLE = '[data-testid="stt-settings-toggle"]'
SEL_START = '[data-testid="stt-start"]'
SEL_PAUSE = '[data-testid="stt-pause"]'
SEL_STATUS = '[data-testid="stt-status"]'
SEL_ROW = '[data-testid="stt-row"]'
SEL_TEXT = '[data-testid="stt-text"]'
SEL_BACKEND_ERROR = '[data-testid="stt-backend-error"]'

#: 배포 UI 행 스크래핑 — 행 컨테이너의 data-trigger + 원문 div 의 텍스트만 뽑는다.
#: 행 전체 innerText 를 쓰면 시각 표시(옵션)와 번역문이 전사에 섞인다.
_DEPLOY_ROW_JS = """els => els.map(e => {
  const t = e.querySelector('[data-testid="stt-text"]');
  return {
    text: ((t ? t.innerText : '') || '').trim(),
    trigger: e.getAttribute('data-trigger') || '',
  };
})"""

_INLINE_ROW_JS = (
    "els => els.map(e => ({ text: (e.innerText || '').trim(), "
    "trigger: e.getAttribute('data-trigger') || '' }))"
)


class HarnessError(RuntimeError):
    """측정 하니스 자체의 고장 — 전사 결과가 아니라 도구가 깨진 경우.

    CLAUDE.md §4: 하니스 버그는 즉시 멈추고 고친다. 이 예외를 빈 전사(WER 100%)로
    삼켜 벤치마크에 기록하면 안 된다.
    """


@dataclass
class TestResult:
    audio_file: str
    transcription: str
    reference: Optional[str]
    wer: Optional[float]


def check_server_health(url: str) -> None:
    """서버 준비 확인. 준비되지 않았으면 RuntimeError."""
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=5) as resp:
            data = json.loads(resp.read())
        if not data.get("ready", False):
            raise RuntimeError("서버가 준비되지 않았습니다 (ready=false). 잠시 후 다시 시도하세요.")
    except RuntimeError:
        raise
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise RuntimeError(f"서버에 연결할 수 없습니다: {url}\n서버가 실행 중인지 확인하세요. ({e})")


def repo_root() -> Path:
    """저장소 루트(= scripts/ 의 부모)."""
    return Path(__file__).resolve().parents[1]


def dist_staleness(root: Optional[Path] = None) -> Optional[str]:
    """배포 UI dist 가 소스보다 오래됐으면 사유 문자열, 아니면 None.

    `frontend/app` 이 없는 환경(배포 PC — dist 만 반입)에서는 검사할 수 없으므로 None.
    """
    root = root or repo_root()
    app = root / "frontend" / "app"
    dist_index = root / "frontend" / "static" / "index.html"
    if not app.is_dir():
        return None  # 소스 트리 없음 = 배포 PC. 검사 불가.
    if not dist_index.is_file():
        return f"배포 UI dist 가 없습니다: {dist_index} — `cd frontend/app && pnpm build` 필요"

    watched: list[Path] = [p for p in (app / "src").rglob("*") if p.is_file()]
    watched += [p for p in (app / "vite.config.ts", app / "package.json", app / "index.html") if p.is_file()]
    if not watched:
        return None
    newest = max(watched, key=lambda p: p.stat().st_mtime)
    if newest.stat().st_mtime > dist_index.stat().st_mtime:
        rel = newest.relative_to(root)
        return f"dist 가 소스보다 오래됐습니다 ({rel} 가 더 최신) — `cd frontend/app && pnpm build` 필요"
    return None


def decode_audio_to_pcm(audio_path: Path):
    """ffmpeg으로 오디오 파일을 16kHz mono int16 PCM numpy 배열로 디코딩."""
    import numpy as np

    cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-f", "s16le",
        "-ar", str(SAMPLE_RATE),
        "-ac", "1",
        "-loglevel", "error",
        "pipe:1",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, check=True)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg을 찾을 수 없습니다. ffmpeg이 PATH에 있는지 확인하세요.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"오디오 디코딩 실패: {e.stderr.decode(errors='replace')}")
    return np.frombuffer(result.stdout, dtype=np.int16)


def compute_wer_score(hypothesis: str, reference: str) -> float:
    """whisperlivekit.metrics.compute_wer로 Word Error Rate 계산."""
    from whisperlivekit.metrics import compute_wer
    return compute_wer(reference.strip(), hypothesis.strip())["wer"]


def find_reference(audio_path: Path) -> Optional[str]:
    """같은 이름의 .txt 정답 파일 탐색."""
    ref_path = audio_path.with_suffix(".txt")
    if ref_path.exists():
        return ref_path.read_text(encoding="utf-8").strip()
    return None


# ── WebSocket 병행 검증 (지표 정본은 어디까지나 DOM) ────────────────────────────
#
# 서버가 보낸 확정 세그먼트와 화면에 그려진 것을 대조해 **프런트 렌더 버그**를 잡는다.
# 과거 내장 UI 의 finalizedHistory 키 충돌이 kor2 WER 을 95.1% 로 부풀린 채 오래 방치된
# 전례가 있다(Exp-181/182). delta 배열 재조립은 하지 않는다 — 순서 재구성 없이 id 별
# last-write-wins 조회표만 만든다(잘못된 재조립이 이 저장소에서 이미 한 번 사고를 냈다,
# frontend/app/src/utils/deltaProtocol.ts 주석 참조).

def _norm(text: str) -> str:
    """공백 정규화 — DOM 줄바꿈과 서버 원문의 공백 차이를 흡수한다."""
    return " ".join((text or "").split())


def collect_ws_finalized(frames: list[str]) -> dict[str, str]:
    """서버 프레임에서 확정 세그먼트 텍스트를 id 별 last-write-wins 로 모은다."""
    found: dict[str, str] = {}
    for raw in frames:
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(msg, dict):
            continue
        for key in ("lines", "new_lines"):
            for seg in msg.get(key) or []:
                if not isinstance(seg, dict):
                    continue
                if not (seg.get("finalized") is True or seg.get("completed") is True):
                    continue
                text = _norm(seg.get("text") or "")
                # 침묵 세그먼트는 배포 UI 가 화면에 내보내지 않는다(transcriptRows.isVisible).
                if not text or seg.get("speaker") == -2:
                    continue
                found[str(seg.get("id"))] = text
    return found


def ws_dom_warnings(rows: list[dict], ws_finalized: dict[str, str], min_len: int = 8) -> list[str]:
    """서버 확정 텍스트 대비 화면 전사의 누락·중복을 경고 문자열로 반환(빈 리스트 = 정상).

    지표를 바꾸지 않는다 — 진단 신호일 뿐이다. 짧은 조각은 우연 일치가 잦아 제외한다.
    """
    dom = _norm(" ".join(r.get("text", "") for r in rows))
    warnings: list[str] = []
    for text in ws_finalized.values():
        if len(text) < min_len:
            continue
        occurrences = dom.count(text)
        if occurrences == 0:
            warnings.append(f"화면 누락: {text[:60]!r}")
        elif occurrences > 1:
            warnings.append(f"화면 중복 x{occurrences}: {text[:60]!r}")
    return warnings


def _resolve_output_device(sd, output_device):
    """장치 이름 문자열이면 WASAPI 출력 인덱스로 해석. 못 찾으면 원값 그대로."""
    if not isinstance(output_device, str):
        return output_device
    devices = sd.query_devices()
    wasapi_idx = next(
        (i for i, d in enumerate(devices)
         if output_device.lower() in d["name"].lower()
         and "wasapi" in sd.query_devices(i, "output").get("hostapi", -1).__class__.__name__.lower()
         and d["max_output_channels"] > 0),
        None,
    )
    if wasapi_idx is None:
        # 폴백: 이름이 포함된 출력 가능 첫 번째 장치
        wasapi_idx = next(
            (i for i, d in enumerate(devices)
             if output_device.lower() in d["name"].lower()
             and d["max_output_channels"] > 0),
            None,
        )
    return wasapi_idx if wasapi_idx is not None else output_device


async def _play_audio(pcm_array, output_device) -> None:
    """VBCable(기본 출력 장치)로 PCM 재생. 블로킹 호출이라 별도 스레드에서 돌린다."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    import sounddevice as sd

    device = _resolve_output_device(sd, output_device)
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=1) as executor:

        def _play():
            sd.play(pcm_array, samplerate=SAMPLE_RATE, device=device)
            sd.wait()

        await loop.run_in_executor(executor, _play)


async def _current_phase(page) -> str:
    """상태 라벨의 raw enum. 오류 경로에서만 쓰므로 조회 실패는 원인 예외를 가리지 않게 삼킨다."""
    try:
        return await page.get_attribute(SEL_STATUS, "data-phase") or "(없음)"
    except Exception:
        return "(상태 요소 없음 — 드로어가 닫혔거나 페이지가 바뀜)"


async def _drive_deploy_ui(page, url: str, pcm_array, output_device, timeout_sec: float) -> list[dict]:
    """배포 UI(React) 구동 — 시작 → 재생 → 일시중단 → 확정 대기 → 스크래핑."""
    import asyncio

    print("[vbcable_test] 배포 UI 로드 중...")
    await page.goto(f"{url}/")
    if DEPLOY_PATH.rstrip("/") not in page.url:
        raise HarnessError(
            f"배포 UI 로 넘어가지 않았습니다 (현재 URL: {page.url}). "
            "dist 가 없어 서버가 내장 UI 로 폴백했을 가능성이 큽니다 — "
            "`cd frontend/app && pnpm build` 후 다시 시도하거나 `--ui inline` 을 쓰세요."
        )

    # 컨트롤은 설정 드로어 안에 있고 드로어는 닫힌 채 시작한다.
    try:
        await page.wait_for_selector(SEL_TOGGLE, timeout=10_000)
        await page.click(SEL_TOGGLE)
        await page.wait_for_selector(SEL_START, timeout=5_000)
    except Exception as e:
        if await page.locator(SEL_BACKEND_ERROR).count() > 0:
            raise HarnessError("백엔드 연결 실패 오버레이가 떠 있습니다 (서버 /health 확인).")
        raise HarnessError(f"설정 드로어를 열지 못했습니다: {e}")

    print("[vbcable_test] 녹음 시작...")
    await page.click(SEL_START)
    # 전역 websocket 변수가 없으므로(zustand 캡슐화) 상태 enum 으로 개통을 확인한다.
    # phase=recording 은 인코더 기동 **후**에 세팅되므로 MediaRecorder 실가동 보장이다.
    try:
        await page.wait_for_selector(f'{SEL_STATUS}[data-phase="recording"]', timeout=20_000)
    except Exception:
        raise HarnessError(
            f"녹음 상태(recording)에 도달하지 못했습니다 (현재 phase={await _current_phase(page)!r})."
        )
    await asyncio.sleep(0.5)  # 캡처 파이프라인 안정화 여유

    duration = len(pcm_array) / SAMPLE_RATE
    print(f"[vbcable_test] 오디오 재생 중 ({duration:.1f}초)...")
    await _play_audio(pcm_array, output_device)

    # "종료"는 화면 전사를 즉시 비우므로(endSession('stop')) 절대 누르지 않는다.
    # 서버 flush 를 기다리며 기록을 화면에 유지하는 "일시 중단"을 쓴다.
    print("[vbcable_test] 녹음 중지(일시중단)...")
    await page.click(SEL_PAUSE)

    print("[vbcable_test] 서버 처리 완료 대기 중...")
    # 서버가 ready_to_stop 을 안 보내도 스토어가 10초 뒤 스스로 paused 로 복구한다
    # (stt.store.ts STOP_FLUSH_TIMEOUT_MS) — 강제 close 해킹이 필요 없다.
    try:
        await page.wait_for_selector(
            f'{SEL_STATUS}[data-phase="paused"]', timeout=max(timeout_sec, 30) * 1000
        )
    except Exception:
        raise HarnessError(
            f"확정(paused) 상태에 도달하지 못했습니다 (현재 phase={await _current_phase(page)!r})"
            " — 프런트 상태머신 정지 의심."
        )

    rows = await page.locator(SEL_ROW).evaluate_all(_DEPLOY_ROW_JS)
    return [r for r in rows if r["text"]]


async def _drive_inline_ui(page, url: str, pcm_array, output_device, timeout_sec: float) -> list[dict]:
    """내장 UI(레거시 데모) 구동 — `/dev` 는 dist 유무와 무관하게 항상 내장 UI 다."""
    import asyncio

    print("[vbcable_test] 내장 UI 로드 중...")
    await page.goto(f"{url}/dev")
    await page.wait_for_selector("#startButton", timeout=10_000)

    print("[vbcable_test] 녹음 시작...")
    await page.click("#startButton")
    # WebSocket이 OPEN 될 때까지 대기 — 캡처 준비 전 재생 시작(레이스)으로 앞부분 유실 방지
    for _ in range(50):  # 최대 ~5초
        try:
            ready = await page.evaluate(
                "typeof websocket !== 'undefined' && websocket && websocket.readyState === 1"
            )
        except Exception:
            ready = False
        if ready:
            break
        await asyncio.sleep(0.1)
    await asyncio.sleep(0.5)

    duration = len(pcm_array) / SAMPLE_RATE
    print(f"[vbcable_test] 오디오 재생 중 ({duration:.1f}초)...")
    await _play_audio(pcm_array, output_device)

    print("[vbcable_test] 녹음 중지(일시중단)...")
    await page.click("#pauseButton")

    print("[vbcable_test] 서버 처리 완료 대기 중...")
    poll_interval = 0.5
    for _ in range(int(max(timeout_sec, 30) / poll_interval)):
        status = await page.text_content("#status") or ""
        if (
            "일시 중단됨" in status
            or "Finished processing" in status
            or "Processing finalized" in status
        ):
            break
        await asyncio.sleep(poll_interval)
    else:
        print("[vbcable_test] 경고: 서버 처리 완료 신호를 받지 못했습니다. WebSocket 강제 닫기 시도.")
        await page.evaluate("if (typeof websocket !== 'undefined' && websocket) { websocket.close(); }")
        await asyncio.sleep(2.0)

    rows = await page.locator("#linesTranscript .textcontent").evaluate_all(_INLINE_ROW_JS)
    return [r for r in rows if r["text"]]


async def run_browser_test(
    audio_path: Path,
    url: str,
    wait_sec: int,
    output_device: str | None,
    *,
    ui: str = "deploy",
    capture_ws: bool = True,
    build_check: bool = True,
    warnings_out: Optional[list] = None,
    fail_screenshot: Optional[Path] = None,
) -> list[dict]:
    """Playwright 헤드풀 브라우저로 VBCable 경로 전사 테스트. 확정 문장+트리거 리스트 반환.

    반환형: [{"text": str, "trigger": str}, ...] — trigger는 문장 DOM의 data-trigger
    속성값(silence/punctuation/language_switch/speaker_change 또는 '')이다.

    ui="deploy"(기본) = 배포 UI(`/wlkies/`), ui="inline" = 내장 UI(`/dev`).
    capture_ws=True 면 서버 프레임을 함께 캡처해 화면과 대조하고, 불일치를 `warnings_out`
    리스트에 담는다(지표는 바꾸지 않는 진단 신호).
    """
    from playwright.async_api import async_playwright

    if ui not in ("deploy", "inline"):
        raise HarnessError(f"알 수 없는 --ui 값: {ui!r} (deploy | inline)")
    if ui == "deploy" and build_check:
        stale = dist_staleness()
        if stale:
            raise HarnessError(stale)

    pcm_array = decode_audio_to_pcm(audio_path)
    frames: list[str] = []
    console_errors: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        try:
            context = await browser.new_context(permissions=["microphone"])
            page = await context.new_page()

            # 프레임 핸들러는 클릭 전에 걸어야 config/초기 snapshot 을 놓치지 않는다.
            if capture_ws:
                def _on_ws(ws):
                    ws.on("framereceived", lambda payload: (
                        frames.append(payload) if isinstance(payload, str) else None
                    ))

                page.on("websocket", _on_ws)

            # 서버가 --pcm-input 모드면 배포 UI 는 조용히 아무것도 보내지 않는다.
            page.on("console", lambda m: (
                console_errors.append(m.text) if "--pcm-input" in m.text else None
            ))

            drive = _drive_deploy_ui if ui == "deploy" else _drive_inline_ui
            try:
                lines = await drive(page, url, pcm_array, output_device, wait_sec)
            except Exception:
                if fail_screenshot is not None:
                    try:
                        fail_screenshot.parent.mkdir(parents=True, exist_ok=True)
                        await page.screenshot(path=str(fail_screenshot))
                        print(f"[vbcable_test] 실패 스크린샷: {fail_screenshot}")
                    except Exception:  # 스크린샷 실패가 원인 예외를 가리지 않게
                        pass
                raise
        finally:
            await browser.close()

    if console_errors:
        raise HarnessError(
            "서버가 --pcm-input 모드로 떠 있어 브라우저 오디오가 전달되지 않습니다: " + console_errors[0]
        )
    if not lines:
        raise HarnessError("전사가 0줄입니다 — 무음 캡처(VBCable 배선) 또는 UI 스크래핑 실패 의심.")

    if capture_ws:
        found = ws_dom_warnings(lines, collect_ws_finalized(frames))
        if warnings_out is not None:
            warnings_out.extend(found)
        for w in found[:5]:
            print(f"[vbcable_test] 경고(WS-DOM 불일치): {w}")

    return lines


async def test_file(
    audio_path: Path,
    url: str,
    wait_sec: int,
    output_device: Optional[str],
    as_json: bool,
    ui: str = "deploy",
) -> TestResult:
    """오디오 파일 1개에 대해 VBCable 경로 전사 테스트 실행."""
    print(f"\n[vbcable_test] {audio_path.name} 테스트 시작 (ui={ui})")
    check_server_health(url)
    reference = find_reference(audio_path)

    lines = await run_browser_test(audio_path, url, wait_sec, output_device, ui=ui)
    sentences = [r["text"] for r in lines]
    transcription = " ".join(sentences)

    wer = None
    if reference:
        wer = compute_wer_score(transcription, reference)

    result = TestResult(
        audio_file=str(audio_path),
        transcription=transcription,
        reference=reference,
        wer=wer,
    )
    print(format_result(result, as_json))
    return result


def format_result(result: TestResult, as_json: bool = False) -> str:
    """테스트 결과를 표준 또는 JSON 형식으로 반환."""
    if as_json:
        data: dict = {
            "file": result.audio_file,
            "transcription": result.transcription,
        }
        if result.reference is not None:
            data["reference"] = result.reference
        if result.wer is not None:
            data["wer"] = round(result.wer, 4)
        return json.dumps(data, ensure_ascii=False, indent=2)

    lines = [f"\n=== 결과: {Path(result.audio_file).name} ==="]
    lines.append(f"전사: {result.transcription}")
    if result.reference is not None:
        lines.append(f"정답: {result.reference}")
    if result.wer is not None:
        lines.append(f"WER:  {result.wer * 100:.1f}%")
    return "\n".join(lines)


def main() -> None:
    import argparse
    import asyncio
    import sys

    parser = argparse.ArgumentParser(
        description="VBCable 브라우저 자동화 전사 테스트. "
                    "서버가 이미 실행 중이어야 하며 VBCable이 Windows 기본 입출력으로 설정되어 있어야 합니다.",
    )
    parser.add_argument("audio_files", nargs="+", type=Path, help="테스트할 오디오 파일 경로")
    parser.add_argument("--url", default="http://localhost:8000", help="서버 URL (기본: http://localhost:8000)")
    parser.add_argument("--wait", type=int, default=15, metavar="SEC", help="재생 완료 후 전사 대기 시간(초, 기본: 15)")
    parser.add_argument(
        "--ui", choices=("deploy", "inline"), default="deploy",
        help="구동할 UI (기본: deploy = 배포 React UI /wlkies/, inline = 내장 데모 UI /dev)",
    )

    def _device(v: str):
        try:
            return int(v)
        except ValueError:
            return v

    parser.add_argument(
        "--output-device", default=None, metavar="DEVICE", type=_device,
        help="sounddevice 출력 장치 이름 또는 인덱스 (기본: 시스템 기본값)",
    )
    parser.add_argument("--json", dest="as_json", action="store_true", help="결과를 JSON 형식으로 출력")
    args = parser.parse_args()

    for audio_file in args.audio_files:
        if not audio_file.exists():
            print(f"[오류] 파일 없음: {audio_file}", file=sys.stderr)
            sys.exit(1)

    results = []
    for audio_file in args.audio_files:
        try:
            result = asyncio.run(
                test_file(audio_file, args.url, args.wait, args.output_device, args.as_json, args.ui)
            )
        except RuntimeError as e:
            print(f"[오류] {audio_file.name}: {e}", file=sys.stderr)
            sys.exit(1)
        results.append(result)

    wer_values = [r.wer for r in results if r.wer is not None]
    if len(results) > 1 and wer_values:
        avg_wer = sum(wer_values) / len(wer_values)
        print(f"\n총 {len(results)}개 파일 완료 | 평균 WER: {avg_wer * 100:.1f}%")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""VBCable 브라우저 자동화 전사 테스트.

전제 조건:
  - Windows 소리 설정에서 VBCable이 기본 입출력으로 설정됨
  - WhisperLiveKit 서버가 localhost:8000에서 실행 중
  - playwright install chromium 실행 완료

사용법:
    python scripts/vbcable_test.py test_data/sbs1.mp3
    python scripts/vbcable_test.py test_data/sbs1.mp3 --wait 30
    python scripts/vbcable_test.py test_data/sbs1.mp3 --json
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


async def run_browser_test(
    audio_path: Path,
    url: str,
    wait_sec: int,
    output_device: str | None,
) -> str:
    """Playwright 헤드풀 브라우저로 VBCable 경로 전사 테스트. 전사 텍스트 반환."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    import sounddevice as sd
    from playwright.async_api import async_playwright

    pcm_array = decode_audio_to_pcm(audio_path)
    duration = len(pcm_array) / SAMPLE_RATE

    processing_timeout_sec = 10
    poll_interval = 0.5

    transcription = ""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        try:
            context = await browser.new_context(permissions=["microphone"])
            page = await context.new_page()

            print("[vbcable_test] 페이지 로드 중...")
            await page.goto(f"{url}/")
            await page.wait_for_selector("#recordButton")

            print("[vbcable_test] 녹음 시작...")
            await page.click("#recordButton")
            await asyncio.sleep(poll_interval)

            print(f"[vbcable_test] 오디오 재생 중 ({duration:.1f}초)...")
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:

                def _play():
                    sd.play(pcm_array, samplerate=SAMPLE_RATE, device=output_device)
                    sd.wait()

                await loop.run_in_executor(executor, _play)

            print(f"[vbcable_test] 재생 완료. 파이프라인 대기 중 (최대 {wait_sec}초)...")
            for _ in range(int(wait_sec / poll_interval)):
                count = await page.locator(".buffer_transcription").count()
                if count == 0:
                    break
                await asyncio.sleep(poll_interval)

            print("[vbcable_test] 녹음 중지...")
            await page.click("#recordButton")

            print("[vbcable_test] 서버 처리 완료 대기 중...")
            for _ in range(int(processing_timeout_sec / poll_interval)):
                status = await page.text_content("#status") or ""
                if "Finished processing" in status:
                    break
                await asyncio.sleep(poll_interval)
            else:
                print("[vbcable_test] 경고: 서버 처리 완료 신호를 받지 못했습니다.")

            transcription = await page.locator("#linesTranscript").inner_text()
        finally:
            await browser.close()

    return (transcription or "").strip()

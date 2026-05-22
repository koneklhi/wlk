"""정답(ground truth)용 오프라인 전사 스크립트.

EN->KO 통역이 교차되는 음성을 위해, 무음(VAD) 기준으로 발화를 청크로 나눠
각 청크마다 언어를 따로 감지/전사한다. whisper transcribe()의 "첫 30초 1개 언어 고정"
한계를 회피하기 위함이다. whisperlivekit 본체는 수정하지 않고 그대로 재사용한다.

사용법:
    python scripts/transcribe_groundtruth.py [audio_path]
기본 audio_path = test_data/ytn1.mp3, 출력은 형제 .txt (문장당 한 줄).
"""

import sys
from pathlib import Path

import numpy as np

from whisperlivekit.silero_vad_iterator import FixedVADIterator, load_jit_vad
from whisperlivekit.whisper import load_model
from whisperlivekit.whisper.audio import SAMPLE_RATE, load_audio
from whisperlivekit.whisper.transcribe import transcribe

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = REPO_ROOT / "whisperlivekit" / "model" / "whisper-large-v3-turbo"

# 청크 병합 파라미터 (필요 시 조정)
VAD_STEP = 512                    # silero VAD 입력 단위(샘플 @16k)
MERGE_GAP_S = 0.6                 # 무음 간격이 이 값 이상이면 청크 분리 (통역 사이 휴지 활용)
MAX_CHUNK_S = 28.0               # 한 청크 최대 길이(초). whisper 30초 윈도 여유
MIN_CHUNK_S = 0.4                # 이보다 짧은 청크는 VAD 블립으로 보고 버림
EDGE_PAD_S = 0.2                 # 청크 앞뒤 패딩(초). 단어 잘림 방지


def detect_speech_segments(audio: np.ndarray) -> list[tuple[int, int]]:
    """silero VAD로 발화 구간 [(start, end)] (샘플 단위)을 수집한다."""
    vad = FixedVADIterator(load_jit_vad())
    vad.reset_states()
    segments: list[tuple[int, int]] = []
    start: int | None = None
    for i in range(0, len(audio), VAD_STEP):
        window = audio[i : i + VAD_STEP]
        res = vad(window)
        if res is None:
            continue
        if "start" in res:
            start = int(res["start"])
        if "end" in res and start is not None:
            segments.append((start, int(res["end"])))
            start = None
    if start is not None:  # 마지막 발화가 안 닫혔으면 파일 끝으로
        segments.append((start, len(audio)))
    return segments


def merge_segments(segments: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """인접 발화를 병합하되 무음 간격/최대 길이 기준으로 분리한다."""
    gap = int(MERGE_GAP_S * SAMPLE_RATE)
    max_len = int(MAX_CHUNK_S * SAMPLE_RATE)
    chunks: list[tuple[int, int]] = []
    for seg_start, seg_end in segments:
        if not chunks:
            chunks.append((seg_start, seg_end))
            continue
        cur_start, cur_end = chunks[-1]
        if seg_start - cur_end <= gap and seg_end - cur_start <= max_len:
            chunks[-1] = (cur_start, seg_end)
        else:
            chunks.append((seg_start, seg_end))
    return chunks


def transcribe_chunk(model, audio: np.ndarray) -> list[str]:
    """청크 오디오를 언어 자동 감지로 전사하고 세그먼트 텍스트 라인을 반환한다."""
    result = transcribe(
        model,
        audio,
        language=None,
        task="transcribe",
        beam_size=5,
        temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
        condition_on_previous_text=True,
        fp16=True,
        verbose=None,
    )
    lines = []
    for seg in result["segments"]:
        text = seg["text"].strip()
        if text:
            lines.append(text)
    return lines


def main() -> None:
    audio_path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "test_data" / "ytn1.mp3"
    out_path = audio_path.with_suffix(".txt")

    print(f"[1/4] 모델 로드: {MODEL_DIR}")
    model = load_model(str(MODEL_DIR))

    print(f"[2/4] 오디오 로드: {audio_path}")
    audio = load_audio(str(audio_path))

    print("[3/4] VAD 발화 구간 감지 + 청크 병합")
    segments = detect_speech_segments(audio)
    chunks = merge_segments(segments)
    min_len = int(MIN_CHUNK_S * SAMPLE_RATE)
    chunks = [c for c in chunks if c[1] - c[0] >= min_len]
    print(f"  발화 구간 {len(segments)}개 -> 청크 {len(chunks)}개")

    print("[4/4] 청크별 언어감지 + 전사")
    pad = int(EDGE_PAD_S * SAMPLE_RATE)
    all_lines: list[str] = []
    for idx, (start, end) in enumerate(chunks, 1):
        clip = audio[max(0, start - pad) : min(len(audio), end + pad)]
        lines = transcribe_chunk(model, clip)
        dur = (end - start) / SAMPLE_RATE
        print(f"  청크 {idx}/{len(chunks)} [{start / SAMPLE_RATE:6.1f}s +{dur:4.1f}s] -> {len(lines)}줄")
        all_lines.extend(lines)

    out_path.write_text("\n\n".join(all_lines) + "\n", encoding="utf-8")
    print(f"\n저장 완료: {out_path} ({len(all_lines)}줄)")


if __name__ == "__main__":
    main()

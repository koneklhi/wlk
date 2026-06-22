"""이중 언어 정답 전사 스크립트.

EN/KO 통역이 교차되는 음성에 대해, 동일 청크를 영어 패스·한국어 패스로 각각 전사한 뒤
타임스탬프 기준으로 병합해 출력한다. 후처리(잘못 전사된 패스 제거)는 사용자가 수행.

사용법:
    python scripts/transcribe_bilingual.py [audio_path]
출력: <audio_path와 동일 디렉터리>/<stem>_bilingual.txt
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

VAD_STEP = 512
MERGE_GAP_S = 0.6
MAX_CHUNK_S = 28.0
MIN_CHUNK_S = 0.4
EDGE_PAD_S = 0.2


def detect_speech_segments(audio: np.ndarray) -> list[tuple[int, int]]:
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
    if start is not None:
        segments.append((start, len(audio)))
    return segments


def merge_segments(segments: list[tuple[int, int]]) -> list[tuple[int, int]]:
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


def transcribe_lang(model, audio: np.ndarray, language: str) -> list[dict]:
    """지정 언어로 전사하고 [{start, end, text}] 리스트를 반환한다."""
    result = transcribe(
        model,
        audio,
        language=language,
        task="transcribe",
        beam_size=5,
        temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
        condition_on_previous_text=True,
        fp16=True,
        verbose=None,
    )
    segs = []
    for seg in result["segments"]:
        text = seg["text"].strip()
        if text:
            segs.append({"start": seg["start"], "end": seg["end"], "text": seg["text"].strip()})
    return segs


def fmt_time(seconds: float) -> str:
    m = int(seconds) // 60
    s = seconds - m * 60
    return f"{m:02d}:{s:05.2f}"


def main() -> None:
    audio_path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "test_data" / "ytn1.mp3"
    out_path = audio_path.with_name(audio_path.stem + "_bilingual.txt")

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

    print("[4/4] 청크별 EN + KO 이중 전사")
    pad = int(EDGE_PAD_S * SAMPLE_RATE)
    all_segs: list[dict] = []

    for idx, (start, end) in enumerate(chunks, 1):
        clip_start = max(0, start - pad)
        clip = audio[clip_start : min(len(audio), end + pad)]
        offset_s = clip_start / SAMPLE_RATE

        en_segs = transcribe_lang(model, clip, "en")
        ko_segs = transcribe_lang(model, clip, "ko")

        dur = (end - start) / SAMPLE_RATE
        print(f"  청크 {idx}/{len(chunks)} [{start / SAMPLE_RATE:6.1f}s +{dur:4.1f}s] EN={len(en_segs)}줄 KO={len(ko_segs)}줄")

        for seg in en_segs:
            all_segs.append({"abs_start": offset_s + seg["start"], "lang": "EN", "text": seg["text"]})
        for seg in ko_segs:
            all_segs.append({"abs_start": offset_s + seg["start"], "lang": "KO", "text": seg["text"]})

    all_segs.sort(key=lambda x: x["abs_start"])

    lines = [f"[{fmt_time(s['abs_start'])} {s['lang']}] {s['text']}" for s in all_segs]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n저장 완료: {out_path} ({len(lines)}줄)")


if __name__ == "__main__":
    main()

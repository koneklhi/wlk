import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel
from starlette.staticfiles import StaticFiles

from whisperlivekit import AudioProcessor, TranscriptionEngine, get_inline_ui_html, parse_args
from whisperlivekit.filtering import get_word_manager
from whisperlivekit.llm_translation import get_prompt_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.getLogger().setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.getLogger("whisperlivekit.qwen3_asr").setLevel(logging.DEBUG)

config = parse_args()
if config.trace_tokens:
    logging.getLogger("whisperlivekit.simul_whisper.backend").setLevel(logging.DEBUG)
    logging.getLogger("whisperlivekit.simul_whisper.align_att_base").setLevel(logging.DEBUG)
    # tokens_alignment의 [Retract]/[RetractScan](Exp-171~ 언어전환 경계 철회 계측)도
    # 이 목록에 없으면 root(WARNING) 레벨에 막혀 logger.info가 조용히 사라진다 — 실측 중
    # 발견(Exp-171 스크리닝, [RetractScan] 0건으로 오인될 뻔함).
    logging.getLogger("whisperlivekit.tokens_alignment").setLevel(logging.DEBUG)
    logger.info("[TraceTokens] DEBUG 레벨 로깅 활성화 (backend + align_att_base + tokens_alignment)")
transcription_engine = None

# 프론트엔드 dist 정적 서빙 게이트 — frontend/static/index.html이 있으면 React dist를 서빙,
# 없으면(개발 환경 등) 기존 내장 데모 UI로 폴백한다.
_frontend_dir = Path(config.frontend_dir).resolve() if getattr(config, "frontend_dir", None) else None
_frontend_enabled = bool(_frontend_dir and (_frontend_dir / "index.html").is_file())

# 세션 언어 오버라이드 허용값(§3.2 한/영 두 언어 + auto). 그 외 값은 무시하고 서버 기본값 사용.
_ALLOWED_SESSION_LANGUAGES = {"auto", "ko", "en"}


class CorrectionUpdate(BaseModel):
    wrong_word: str
    correct_word: str


class PromptItemRequest(BaseModel):
    block_key: str            # "glossary_block" 또는 "sentence_block"
    origin: str
    translation: Optional[str] = None


class TranscriptLine(BaseModel):
    speaker: int
    text: str
    translation: Optional[str] = None


class SaveTranscriptRequest(BaseModel):
    lines: List[TranscriptLine]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global transcription_engine
    transcription_engine = TranscriptionEngine(config=config)
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# React dist의 /assets을 마운트 (assets 디렉토리가 실제로 없으면 건너뛰어 기동 실패 방지).
if _frontend_enabled:
    _frontend_assets_dir = _frontend_dir / "assets"
    if _frontend_assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_frontend_assets_dir)), name="frontend_assets")

@app.get("/")
async def get():
    if _frontend_enabled:
        return FileResponse(_frontend_dir / "index.html")
    return HTMLResponse(get_inline_ui_html())


@app.get("/health")
async def health():
    """Health check endpoint."""
    global transcription_engine
    backend = getattr(transcription_engine.config, "backend", "whisper") if transcription_engine else None
    return JSONResponse({
        "status": "ok",
        "backend": backend,
        "ready": transcription_engine is not None,
    })


async def handle_websocket_results(websocket, results_generator, diff_tracker=None, audio_processor=None):
    """Consumes results from the audio processor and sends them via WebSocket."""
    try:
        async for response in results_generator:
            session_start = getattr(audio_processor, "beg_loop", None)
            if diff_tracker is not None:
                await websocket.send_json(diff_tracker.to_message(response, session_start))
            else:
                await websocket.send_json(response.to_dict(session_start))
        # when the results_generator finishes it means all audio has been processed
        logger.info("Results generator finished. Sending 'ready_to_stop' to client.")
        await websocket.send_json({"type": "ready_to_stop"})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected while handling results (client likely closed connection).")
    except Exception as e:
        logger.exception(f"Error in WebSocket results handler: {e}")


@app.websocket("/asr")
async def websocket_endpoint(websocket: WebSocket):
    global transcription_engine

    # Read per-session options from query parameters
    session_language = websocket.query_params.get("language", None)
    if session_language is not None:
        normalized = session_language.strip().lower()
        if normalized in _ALLOWED_SESSION_LANGUAGES:
            session_language = normalized
        else:
            logger.warning(
                "[SessionLang] 허용되지 않은 language=%r — 무시하고 서버 기본값 사용",
                session_language,
            )
            session_language = None
    mode = websocket.query_params.get("mode", "full")

    audio_processor = AudioProcessor(
        transcription_engine=transcription_engine,
        language=session_language,
    )
    await websocket.accept()
    logger.info(
        "WebSocket connection opened.%s",
        f" language={session_language}" if session_language else "",
    )
    diff_tracker = None
    if mode == "diff":
        from whisperlivekit.diff_protocol import DiffTracker
        diff_tracker = DiffTracker()
        logger.info("Client requested diff mode")

    try:
        await websocket.send_json({
            "type": "config",
            "useAudioWorklet": bool(config.pcm_input),
            "mode": mode,
            "language": session_language if session_language is not None else getattr(config, "lan", "auto"),
        })
    except Exception as e:
        logger.warning(f"Failed to send config to client: {e}")

    results_generator = await audio_processor.create_tasks()
    websocket_task = asyncio.create_task(handle_websocket_results(websocket, results_generator, diff_tracker, audio_processor))

    try:
        while True:
            message = await websocket.receive_bytes()
            await audio_processor.process_audio(message)
    except KeyError as e:
        if 'bytes' in str(e):
            logger.warning("Client has closed the connection.")
        else:
            logger.error(f"Unexpected KeyError in websocket_endpoint: {e}", exc_info=True)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client during message receiving loop.")
    except Exception as e:
        logger.error(f"Unexpected error in websocket_endpoint main loop: {e}", exc_info=True)
    finally:
        logger.info("Cleaning up WebSocket endpoint...")
        if not websocket_task.done():
            websocket_task.cancel()
        try:
            await websocket_task
        except asyncio.CancelledError:
            logger.info("WebSocket results handler task was cancelled.")
        except Exception as e:
            logger.warning(f"Exception while awaiting websocket_task completion: {e}")

        await audio_processor.cleanup()
        logger.info("WebSocket endpoint cleaned up successfully.")


# ---------------------------------------------------------------------------
# Deepgram-compatible WebSocket API  (/v1/listen)
# ---------------------------------------------------------------------------

@app.websocket("/v1/listen")
async def deepgram_websocket_endpoint(websocket: WebSocket):
    """Deepgram-compatible live transcription WebSocket."""
    global transcription_engine
    from whisperlivekit.deepgram_compat import handle_deepgram_websocket
    await handle_deepgram_websocket(websocket, transcription_engine, config)


# ---------------------------------------------------------------------------
# OpenAI-compatible REST API  (/v1/audio/transcriptions)
# ---------------------------------------------------------------------------

async def _convert_to_pcm(audio_bytes: bytes) -> bytes:
    """Convert any audio format to PCM s16le mono 16kHz using ffmpeg."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", "pipe:0",
        "-f", "s16le", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        "-loglevel", "error",
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(input=audio_bytes)
    if proc.returncode != 0:
        raise HTTPException(status_code=400, detail=f"Audio conversion failed: {stderr.decode().strip()}")
    return stdout


def _parse_time_str(time_str: str) -> float:
    """Parse 'H:MM:SS.cc' to seconds."""
    parts = time_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


def _format_openai_response(front_data, response_format: str, language: Optional[str], duration: float) -> dict:
    """Convert FrontData to OpenAI-compatible response."""
    d = front_data.to_dict()
    lines = d.get("lines", [])

    # Combine all speech text (exclude silence segments)
    text_parts = [l["text"] for l in lines if l.get("text") and l.get("speaker", 0) != -2]
    full_text = " ".join(text_parts).strip()

    if response_format == "text":
        return full_text

    # Build segments and words for verbose_json
    segments = []
    words = []
    for i, line in enumerate(lines):
        if line.get("speaker") == -2 or not line.get("text"):
            continue
        start = _parse_time_str(line.get("start", "0:00:00"))
        end = _parse_time_str(line.get("end", "0:00:00"))
        segments.append({
            "id": len(segments),
            "start": round(start, 2),
            "end": round(end, 2),
            "text": line["text"],
        })
        # Split segment text into approximate words with estimated timestamps
        seg_words = line["text"].split()
        if seg_words:
            word_duration = (end - start) / max(len(seg_words), 1)
            for j, word in enumerate(seg_words):
                words.append({
                    "word": word,
                    "start": round(start + j * word_duration, 2),
                    "end": round(start + (j + 1) * word_duration, 2),
                })

    if response_format == "verbose_json":
        return {
            "task": "transcribe",
            "language": language or "unknown",
            "duration": round(duration, 2),
            "text": full_text,
            "words": words,
            "segments": segments,
        }

    if response_format in ("srt", "vtt"):
        lines_out = []
        if response_format == "vtt":
            lines_out.append("WEBVTT\n")
        for i, seg in enumerate(segments):
            start_ts = _srt_timestamp(seg["start"], response_format)
            end_ts = _srt_timestamp(seg["end"], response_format)
            if response_format == "srt":
                lines_out.append(f"{i + 1}")
            lines_out.append(f"{start_ts} --> {end_ts}")
            lines_out.append(seg["text"])
            lines_out.append("")
        return "\n".join(lines_out)

    # Default: json
    return {"text": full_text}


def _srt_timestamp(seconds: float, fmt: str) -> str:
    """Format seconds as SRT (HH:MM:SS,mmm) or VTT (HH:MM:SS.mmm) timestamp."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds % 1) * 1000))
    sep = "," if fmt == "srt" else "."
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


@app.post("/v1/audio/transcriptions")
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form(default=""),
    language: Optional[str] = Form(default=None),
    prompt: str = Form(default=""),
    response_format: str = Form(default="json"),
    timestamp_granularities: Optional[List[str]] = Form(default=None),
):
    """OpenAI-compatible audio transcription endpoint.

    Accepts the same parameters as OpenAI's /v1/audio/transcriptions API.
    The `model` parameter is accepted but ignored (uses the server's configured backend).
    """
    global transcription_engine

    audio_bytes = await file.read()
    if not audio_bytes:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Empty audio file")

    # Convert to PCM for pipeline processing
    pcm_data = await _convert_to_pcm(audio_bytes)
    duration = len(pcm_data) / (16000 * 2)  # 16kHz, 16-bit

    # Process through the full pipeline
    processor = AudioProcessor(
        transcription_engine=transcription_engine,
        language=language,
    )
    # Force PCM input regardless of server config
    processor.is_pcm_input = True

    results_gen = await processor.create_tasks()

    # Collect results in background while feeding audio
    final_result = None

    async def collect():
        nonlocal final_result
        async for result in results_gen:
            final_result = result

    collect_task = asyncio.create_task(collect())

    # Feed audio in chunks (1 second each)
    chunk_size = 16000 * 2  # 1 second of PCM
    for i in range(0, len(pcm_data), chunk_size):
        await processor.process_audio(pcm_data[i:i + chunk_size])

    # Signal end of audio
    await processor.process_audio(b"")

    # Wait for pipeline to finish
    try:
        await asyncio.wait_for(collect_task, timeout=120.0)
    except asyncio.TimeoutError:
        logger.warning("Transcription timed out after 120s")
    finally:
        await processor.cleanup()

    if final_result is None:
        return JSONResponse({"text": ""})

    result = _format_openai_response(final_result, response_format, language, duration)

    if isinstance(result, str):
        return PlainTextResponse(result)
    return JSONResponse(result)


@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible model listing endpoint."""
    global transcription_engine
    backend = getattr(transcription_engine.config, "backend", "whisper") if transcription_engine else "whisper"
    model_size = getattr(transcription_engine.config, "model_size", "base") if transcription_engine else "base"
    return JSONResponse({
        "object": "list",
        "data": [{
            "id": f"{backend}/{model_size}" if backend != "whisper" else f"whisper-{model_size}",
            "object": "model",
            "owned_by": "whisperlivekit",
        }],
    })


# ---------------------------------------------------------------------------
# Word Correction Management REST API  (/api/corrections)
# ---------------------------------------------------------------------------

@app.get("/api/corrections")
async def get_corrections():
    """사용자 단어 교정 사전 조회."""
    word_manager = get_word_manager()
    return word_manager.user_replacements


@app.post("/api/corrections")
async def add_correction(update: CorrectionUpdate):
    """단어 교정 추가. 즉시 반영."""
    word_manager = get_word_manager()
    word_manager.add_user_word(update.wrong_word, update.correct_word)
    return {"status": "success"}


@app.delete("/api/corrections/{wrong_word}")
async def delete_correction(wrong_word: str):
    """단어 교정 삭제. 즉시 반영."""
    word_manager = get_word_manager()
    word_manager.delete_user_word(wrong_word)
    return {"status": "success"}


# ---------------------------------------------------------------------------
# Translation Glossary Management REST API  (/api/prompts)
# ---------------------------------------------------------------------------

@app.get("/api/prompts")
async def get_prompts():
    """사용자 뷰: glossary는 사용자 추가분만, sentence는 전체(기본+사용자) 반환."""
    return get_prompt_manager().get_user_view_settings()


@app.post("/api/prompts/add-item")
async def add_prompt_item(request: PromptItemRequest):
    """glossary_block 또는 sentence_block에 항목 추가. 즉시 반영."""
    if request.block_key not in ("glossary_block", "sentence_block"):
        raise HTTPException(status_code=400, detail="Invalid block key")
    if request.translation is None:
        raise HTTPException(status_code=400, detail="translation is required for add-item")
    get_prompt_manager().add_item(request.block_key, request.origin, request.translation)
    return {"status": "success"}


@app.post("/api/prompts/delete-item")
async def delete_prompt_item(request: PromptItemRequest):
    """glossary_block 또는 sentence_block에서 항목 삭제. 즉시 반영."""
    if request.block_key not in ("glossary_block", "sentence_block"):
        raise HTTPException(status_code=400, detail="Invalid block key")
    success = get_prompt_manager().remove_item(request.block_key, request.origin)
    if success:
        return {"status": "success"}
    return {"status": "warning", "message": "Item not found or cannot delete default glossary item"}


# ---------------------------------------------------------------------------
# Transcript Save API  (/api/save-transcript) — 저장 버튼 클릭 시 프론트가 호출
# ---------------------------------------------------------------------------

@app.post("/api/save-transcript")
async def save_transcript(req: SaveTranscriptRequest):
    """저장 버튼 클릭 시 누적 전사를 서버 로컬 폴더에 .txt로 저장 (화자+텍스트+번역)."""
    save_dir = Path(config.transcript_save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = save_dir / f"transcript_{ts}.txt"
    out = []
    for ln in req.lines:
        if not ln.text:
            continue
        out.append(f"[화자 {ln.speaker}] {ln.text}")
        if ln.translation:
            out.append(f"    ↳ {ln.translation}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return {"status": "success", "path": str(path.resolve()), "line_count": len(req.lines)}


# ---------------------------------------------------------------------------
# React SPA fallback — 반드시 파일의 다른 모든 @app.get(...) 라우트보다 뒤에 위치해야 한다.
# 위 API/WS 라우트에 매칭되지 않는 나머지 GET 요청을 index.html로 돌려
# 클라이언트 사이드 라우팅(react-router 등)이 새로고침에도 동작하게 한다.
# ---------------------------------------------------------------------------

if _frontend_enabled:
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        return FileResponse(_frontend_dir / "index.html")


def main():
    """Entry point for the CLI command."""
    import uvicorn

    from whisperlivekit.cli import print_banner

    ssl = bool(config.ssl_certfile and config.ssl_keyfile)
    print_banner(config, config.host, config.port, ssl=ssl)

    uvicorn_kwargs = {
        "app": "whisperlivekit.basic_server:app",
        "host": config.host,
        "port": config.port,
        "reload": False,
        "log_level": "info",
        "lifespan": "on",
    }

    ssl_kwargs = {}
    if config.ssl_certfile or config.ssl_keyfile:
        if not (config.ssl_certfile and config.ssl_keyfile):
            raise ValueError("Both --ssl-certfile and --ssl-keyfile must be specified together.")
        ssl_kwargs = {
            "ssl_certfile": config.ssl_certfile,
            "ssl_keyfile": config.ssl_keyfile,
        }

    if ssl_kwargs:
        uvicorn_kwargs = {**uvicorn_kwargs, **ssl_kwargs}
    if config.forwarded_allow_ips:
        uvicorn_kwargs = {**uvicorn_kwargs, "forwarded_allow_ips": config.forwarded_allow_ips}

    uvicorn.run(**uvicorn_kwargs)

if __name__ == "__main__":
    main()

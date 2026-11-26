import logging
from io import BytesIO
from typing import List, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from pypdf import PdfReader

from app.config import settings
from app.database import DatabaseUnavailable, database
from app.gemini import GeminiUnavailable, generate_reply, synthesize_speech
from app.rag import build_grounded_prompt, retrieve_relevant, split_text

logger = logging.getLogger(__name__)
app = FastAPI(title="Multimodal Support Chatbot API", version="0.1.0")

IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
AUDIO_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
}
DOCUMENT_TYPES = {".pdf": "application/pdf", ".txt": "text/plain"}


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def _extension(filename: str) -> str:
    return "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


async def _read_limited(upload: UploadFile) -> bytes:
    data = await upload.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds the upload size limit.")
    return data


def _validate_media(filename: str, content_type: str, allowed: dict) -> str:
    extension = _extension(filename)
    expected_type = allowed.get(extension)
    if not expected_type or content_type not in {expected_type, "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Unsupported file type.")
    return expected_type


def _validate_signature(data: bytes, mime_type: str):
    is_mpeg_audio = (
        len(data) >= 2
        and data[0] == 0xFF
        and data[1] & 0xE0 == 0xE0
    )
    signatures = {
        "image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": data.startswith(b"\xff\xd8\xff"),
        "image/webp": len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
        "application/pdf": data.startswith(b"%PDF-"),
        "audio/wav": data.startswith(b"RIFF") and data[8:12] == b"WAVE",
        "audio/ogg": data.startswith(b"OggS"),
        "audio/mpeg": data.startswith(b"ID3") or is_mpeg_audio,
        "audio/mp4": len(data) >= 8 and data[4:8] == b"ftyp",
        "audio/webm": data.startswith(b"\x1a\x45\xdf\xa3"),
    }
    if mime_type in signatures and not signatures[mime_type]:
        raise HTTPException(status_code=415, detail="File content does not match its declared type.")


def _extract_document(mime_type: str, data: bytes) -> List[Tuple[Optional[int], str]]:
    try:
        if mime_type == "application/pdf":
            reader = PdfReader(BytesIO(data), strict=True)
            pages = [(index + 1, page.extract_text() or "") for index, page in enumerate(reader.pages)]
        else:
            pages = [(None, data.decode("utf-8-sig"))]
    except Exception as exc:
        logger.warning("Document extraction failed (%s).", type(exc).__name__)
        raise HTTPException(status_code=400, detail="Could not read this document.") from exc

    chunks = []
    for page_number, text in pages:
        chunks.extend((page_number, chunk) for chunk in split_text(text))
    if not chunks:
        raise HTTPException(status_code=400, detail="No readable text was found in the document.")
    return chunks


@app.get("/health")
def health():
    db_ready = False
    try:
        database.check_connection()
        db_ready = True
    except DatabaseUnavailable:
        pass
    return {
        "status": "ready" if db_ready and settings.gemini_api_key else "degraded",
        "mysql_ready": db_ready,
        "gemini_configured": bool(settings.gemini_api_key),
    }


@app.post("/api/chat")
async def chat(
    message: str = Form(..., min_length=1, max_length=4000),
    image: Optional[UploadFile] = File(None),
    audio: Optional[UploadFile] = File(None),
):
    media = []
    for upload, allowed in ((image, IMAGE_TYPES), (audio, AUDIO_TYPES)):
        if upload is None:
            continue
        mime_type = _validate_media(upload.filename or "", upload.content_type or "", allowed)
        data = await _read_limited(upload)
        _validate_signature(data, mime_type)
        media.append((data, mime_type))

    try:
        candidates = database.search_candidates()
        relevant = retrieve_relevant(message, candidates)
        prompt = build_grounded_prompt(message, relevant)
        answer = generate_reply(prompt, media)
        sources = []
        seen = set()
        for chunk in relevant:
            key = (chunk["filename"], chunk.get("page_number"))
            if key not in seen:
                seen.add(key)
                sources.append({"filename": key[0], "page": key[1]})
        return {"reply": answer, "sources": sources}
    except DatabaseUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GeminiUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    filename = (file.filename or "").replace("\\", "/").split("/")[-1]
    if not filename or len(filename) > 255:
        raise HTTPException(status_code=400, detail="Filename must be between 1 and 255 characters.")
    mime_type = _validate_media(filename, file.content_type or "", DOCUMENT_TYPES)
    data = await _read_limited(file)
    if mime_type == "application/pdf":
        _validate_signature(data, mime_type)
    elif b"\x00" in data:
        raise HTTPException(status_code=415, detail="Text documents must be UTF-8 encoded.")

    chunks = _extract_document(mime_type, data)
    try:
        document_id = database.add_document(filename, mime_type, chunks)
        return {"id": document_id, "filename": filename, "chunks": len(chunks)}
    except DatabaseUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/documents")
def list_documents():
    try:
        return {"documents": database.list_documents()}
    except DatabaseUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/speech")
def speech(request: SpeechRequest):
    try:
        audio, mime_type = synthesize_speech(request.text)
        return Response(content=audio, media_type=mime_type)
    except GeminiUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

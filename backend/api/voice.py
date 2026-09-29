"""
Voice API endpoints (optional feature).

POST /voice/transcribe    Audio → text
POST /voice/synthesize    Text → audio
GET  /voice/status        Check availability
"""
import logging
from fastapi import APIRouter, HTTPException, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from backend.services.voice_service import get_voice_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])


class SynthesizeRequest(BaseModel):
    text: str


@router.get("/status")
def voice_status():
    svc = get_voice_service()
    return svc.get_status()


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    svc = get_voice_service()
    status = svc.get_status()
    if not status["stt_available"]:
        raise HTTPException(
            status_code=503,
            detail=status.get("error", "Speech-to-text not available."),
        )

    content = await file.read()
    transcript, error = svc.transcribe_audio(content)
    if error:
        raise HTTPException(status_code=500, detail=error)
    return {"transcript": transcript}


@router.post("/synthesize")
def synthesize_speech(req: SynthesizeRequest):
    svc = get_voice_service()
    status = svc.get_status()
    if not status["tts_available"]:
        raise HTTPException(
            status_code=503,
            detail=status.get("error", "Text-to-speech not available."),
        )

    audio_bytes, error = svc.synthesize_speech(req.text)
    if error:
        raise HTTPException(status_code=500, detail=error)
    return Response(content=audio_bytes, media_type="audio/wav")

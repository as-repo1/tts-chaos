import json
import logging
import re
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.app.services.generator import generate_audio_asset

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["stream"])

@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established")
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            text = payload.get("text", "")
            model_id = payload.get("model_id")
            voice_id = payload.get("voice_id", "auto")
            speed = float(payload.get("speed", 1.0))
            pitch = float(payload.get("pitch", 0.0))
            language = payload.get("language", "en")
            
            if not model_id:
                from backend.app.services.model_selector import auto_select_model
                from backend.app.services.model_manager import model_manager
                model_id = auto_select_model(text, language, "neutral", model_manager)
            
            if not text:
                await websocket.send_json({"type": "error", "message": "Empty text"})
                continue
                
            # Naive chunking for low-latency streaming
            # Split by punctuation
            sentences = re.split(r'(?<=[.!?])\s+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if not sentences:
                continue
                
            await websocket.send_json({"type": "start", "chunks": len(sentences)})
            
            for i, sentence in enumerate(sentences):
                # Generate each chunk
                result = generate_audio_asset(
                    text=sentence,
                    voice_name="stream_chunk",
                    language=language,
                    style="neutral",
                    model_id=model_id,
                    voice_id=voice_id,
                    speed=speed,
                    pitch=pitch,
                    output_format="wav" # standard for streaming to Web Audio API
                )
                
                # Read raw bytes and send as binary over the websocket
                with open(result["file_path"], "rb") as f:
                    audio_bytes = f.read()
                    
                # Clean up the file to avoid filling up disk
                from backend.app.services.generator import delete_audio_file
                delete_audio_file(result["file_path"])
                    
                # We can send a JSON header, then the binary payload
                await websocket.send_json({
                    "type": "chunk_meta", 
                    "index": i, 
                    "text": sentence
                })
                await websocket.send_bytes(audio_bytes)
                
            await websocket.send_json({"type": "done"})
            
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass

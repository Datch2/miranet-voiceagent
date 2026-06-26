import sys
import pathlib
import uuid
import json
import logging
import time
import os
import psutil
from contextlib import asynccontextmanager

# Resolve and add parent directory to system path for clean imports of 'backend' package
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.db.database import db
from backend.agents import (
    TranscriberAgent,
    ClassifierAgent,
    ResponderAgent,
    OrchestratorAgent
)


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("MiranetVoiceAgentServer")

# Global instances of agents
transcriber = TranscriberAgent()
classifier = ClassifierAgent()
responder = ResponderAgent()
orchestrator: OrchestratorAgent | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifespans."""
    global orchestrator
    
    logger.info("Initializing Miranet VoiceAgent server lifecycles...")
    try:
        # 1. Connect to Database Pool
        await db.connect()
        
        # 2. Load Whisper Model (Async wrap)
        await transcriber.load()
        
        # 3. Instantiate Orchestrator
        orchestrator = OrchestratorAgent(
            transcriber=transcriber,
            classifier=classifier,
            responder=responder
        )
        
        logger.info("Server initialization complete. Ready for connections.")
        yield
        
    except Exception as e:
        logger.critical(f"Critical error during server startup: {e}", exc_info=True)
        raise
    finally:
        # Shutdown phase
        logger.info("Shutting down Miranet VoiceAgent server lifecycles...")
        # 1. Disconnect Database Pool
        await db.disconnect()
        # 2. Close LLM agent connection clients
        await classifier.close()
        await responder.close()
        logger.info("Server shutdown complete.")

# Initialize FastAPI App
app = FastAPI(
    title="Miranet VoiceAgent Platform API",
    description="Asynchronous Real-Time Voice Agent with FastAPI, WebSockets, Whisper, and Ollama.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for external/remote static hosts
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve dynamic path to frontend directory (cross-platform compatible)
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

# Serve static files from the frontend directory
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
async def get_index():
    """Serves the main frontend page."""
    return FileResponse(str(FRONTEND_DIR / "index.html"))

@app.get("/index.css")
async def get_css():
    """Serve CSS directly for relative paths."""
    return FileResponse(str(FRONTEND_DIR / "index.css"))

@app.get("/index.js")
async def get_js():
    """Serve JS directly for relative paths."""
    return FileResponse(str(FRONTEND_DIR / "index.js"))

@app.get("/agent.html")
async def get_agent_html():
    """Serves the agent dashboard page."""
    return FileResponse(str(FRONTEND_DIR / "agent.html"))

@app.get("/agent")
async def get_agent():
    """Serves the agent dashboard page."""
    return FileResponse(str(FRONTEND_DIR / "agent.html"))



@app.get("/health", tags=["System"])
async def health_check():
    """Simple API status checker."""
    db_status = "healthy" if (db.pool is not None or db.use_supabase or db.use_sqlite) else "disconnected"
    return JSONResponse(
        content={
            "status": "online",
            "database": db_status,
            "config": {
                "whisper_model": settings.WHISPER_MODEL_NAME,
                "ollama_model": settings.OLLAMA_MODEL,
                "torch_threads": settings.TORCH_NUM_THREADS
            }
        },
        status_code=200
    )

@app.get("/api/v1/cliente/buscar", tags=["Cliente"])
async def buscar_cliente(type: str, value: str):
    """
    Endpoint to validate customer identity (by DNI or Router SN)
    strictly against the business database.
    """
    logger.info(f"Client lookup requested: type={type}, value={value}")
    try:
        client = await db.get_client_by_identifier(type, value)
        if client:
            return JSONResponse(
                content={
                    "status": "found",
                    "client": client
                },
                status_code=200
            )
        else:
            return JSONResponse(
                content={
                    "status": "not_found",
                    "message": "Client not found in business records."
                },
                status_code=404
            )
    except Exception as e:
        logger.error(f"Error searching client: {e}", exc_info=True)
        return JSONResponse(
            content={
                "status": "error",
                "message": "Internal server database error."
            },
            status_code=500
        )

@app.get("/api/v1/sistema/status", tags=["System"])
async def system_status():
    """
    Diagnostic endpoint to verify both business and telemetry connections.
    """
    negocio_status = "conectado (port 3307)" if (db.pool_negocio or db.use_sqlite) else "desconectado"
    telemetria_status = "conectado (port 3307)" if (db.pool_telemetria or db.use_sqlite) else "desconectado"

    return JSONResponse(
        content={
            "status": "online",
            "database_negocio": negocio_status,
            "database_telemetria": telemetria_status
        },
        status_code=200
    )

@app.get("/api/v1/sistema/telemetria", tags=["System"])
async def obtener_telemetria():
    """
    Retrieves all SNMP telemetry events logged in the Cacti database.
    """
    if db.pool_telemetria:
        try:
            async with db.pool_telemetria.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT id, router_id, latencia, recorded_at FROM telemetria_snmp ORDER BY id DESC;")
                    rows = await cur.fetchall()
                    for r in rows:
                        r["recorded_at"] = r["recorded_at"].isoformat()
                    return JSONResponse(content=rows, status_code=200)
        except Exception as e:
            logger.error(f"Error fetching telemetry from MySQL cacti: {e}")
            return JSONResponse(content={"error": str(e)}, status_code=500)
    elif db.use_sqlite:
        import sqlite3
        def _fetch():
            conn = sqlite3.connect(db.sqlite_path_telemetria)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT id, router_id, latencia, recorded_at FROM telemetria_snmp ORDER BY id DESC;")
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()
        try:
            rows = await asyncio.to_thread(_fetch)
            return JSONResponse(content=rows, status_code=200)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)
    else:
        return JSONResponse(content=[], status_code=200)

@app.websocket("/ws")
@app.websocket("/ws/voice")
async def websocket_voice_endpoint(
    websocket: WebSocket,
    session_id: str | None = Query(None),
    login_type: str | None = Query(None),
    login_value: str | None = Query(None)
):
    """
    WebSocket endpoint for real-time binary audio streaming.
    
    Accepts:
        - Binary PCM 16-bit 16kHz mono audio chunks.
        - Text commands (JSON format) like 'end_of_speech' to trigger generation.
    """
    await websocket.accept()
    
    # Establish or generate a session ID
    if not session_id:
        session_id = f"session_{uuid.uuid4().hex[:8]}"

    logger.info(f"New WebSocket client connected. Assigned Session ID: {session_id} (Login: {login_type}={login_value})")

    # Register session in Orchestrator
    try:
        await orchestrator.start_session(session_id, login_type, login_value)
    except Exception as e:
        logger.error(f"Failed to start session {session_id} in orchestrator: {e}")
        await websocket.close(code=1011, reason="Session initialization failed.")
        return

    try:
        while True:
            # Wait for any input from the client (binary audio chunk or text controls)
            message = await websocket.receive()
            
            # 1. Handle Binary Audio Stream
            if "bytes" in message:
                chunk = message["bytes"]
                try:
                    metrics = await orchestrator.append_audio_chunk(
                        session_id=session_id,
                        chunk=chunk
                    )
                    # Feed back network diagnostics in real time
                    await websocket.send_json({
                        "type": "network_status",
                        "metrics": metrics
                    })
                except Exception as e:
                    logger.error(f"Error handling audio chunk for session {session_id}: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Error processing audio package."
                    })
            
            # 2. Handle Text Control Messages
            elif "text" in message:
                text_msg = message["text"]
                try:
                    control = json.loads(text_msg)
                    cmd_type = control.get("type")
                    
                    if cmd_type == "end_of_speech":
                        tiempo_inicio = time.time()
                        logger.info(f"Client declared end of speech for {session_id}. Processing segment...")
                        
                        # Determine audio duration in seconds
                        duracion_audio = control.get("duracion_audio")
                        if duracion_audio is None:
                            session = orchestrator.active_sessions.get(session_id)
                            if session and "audio_buffer" in session:
                                # PCM 16-bit 16kHz mono audio (2 bytes per sample, 16000 samples/sec -> 32000 bytes/sec)
                                duracion_audio = len(session["audio_buffer"]) / 32000.0
                            else:
                                duracion_audio = 1.0
                        else:
                            try:
                                duracion_audio = float(duracion_audio)
                            except (ValueError, TypeError):
                                duracion_audio = 1.0
                        if duracion_audio <= 0:
                            duracion_audio = 1.0

                        # Process the accumulated audio buffer
                        result = await orchestrator.process_audio_segment(session_id)
                        
                        # Calculate response metrics
                        tiempo_total = time.time() - tiempo_inicio
                        rtf_calculado = tiempo_total / duracion_audio
                        memoria_ram = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

                        # Send result back to the user
                        await websocket.send_json({
                            "type": "agent_response",
                            "transcription": result["transcription"],
                            "response": result["response"],
                            "intent": result["intent"],
                            "sentiment": result["sentiment"],
                            "latencies": result["latencies"],
                            "client_info": result.get("client_info"),
                            "network_status": result.get("network_status"),
                            "diagnostico_causa_raiz": result.get("diagnostico_causa_raiz"),
                            "porcentaje_confianza": result.get("porcentaje_confianza"),
                            "metricas_agente": {
                                "latencia_p95_ms": tiempo_total * 1000,
                                "rtf": rtf_calculado,
                                "ram_consumo_mb": memoria_ram
                            }
                        })
                        
                    elif cmd_type == "user_transcription":
                        tiempo_inicio = time.time()
                        transcription_text = control.get("text", "").strip()
                        logger.info(f"Client sent direct transcription for {session_id}: '{transcription_text}'")
                        
                        # Determine audio duration in seconds
                        duracion_audio = control.get("duracion_audio")
                        if duracion_audio is None:
                            # Estimate duration based on text length (e.g. typical speech rate: 150 words per minute / 2.5 words per second)
                            words_count = len(transcription_text.split())
                            duracion_audio = max(1.0, words_count / 2.5)
                        else:
                            try:
                                duracion_audio = float(duracion_audio)
                            except (ValueError, TypeError):
                                duracion_audio = 1.0
                        if duracion_audio <= 0:
                            duracion_audio = 1.0

                        # Process using the direct text route
                        result = await orchestrator.process_text_segment(session_id, transcription_text)
                        
                        # Calculate response metrics
                        tiempo_total = time.time() - tiempo_inicio
                        rtf_calculado = tiempo_total / duracion_audio
                        memoria_ram = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

                        # Send result back to the user
                        await websocket.send_json({
                            "type": "agent_response",
                            "transcription": result["transcription"],
                            "response": result["response"],
                            "intent": result["intent"],
                            "sentiment": result["sentiment"],
                            "latencies": result["latencies"],
                            "client_info": result.get("client_info"),
                            "network_status": result.get("network_status"),
                            "diagnostico_causa_raiz": result.get("diagnostico_causa_raiz"),
                            "porcentaje_confianza": result.get("porcentaje_confianza"),
                            "metricas_agente": {
                                "latencia_p95_ms": tiempo_total * 1000,
                                "rtf": rtf_calculado,
                                "ram_consumo_mb": memoria_ram
                            }
                        })
                        
                    elif cmd_type == "reset":
                        # Empty current in-memory buffer for user
                        if session_id in orchestrator.active_sessions:
                            orchestrator.active_sessions[session_id]["audio_buffer"] = bytearray()
                        await websocket.send_json({
                            "type": "status",
                            "message": "Audio buffer cleared."
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unsupported control type: {cmd_type}"
                        })
                except json.JSONDecodeError:
                    logger.warning(f"Received malformed text command: {text_msg}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Malformed JSON payload."
                    })
                except Exception as e:
                    logger.error(f"Error handling text command for session {session_id}: {e}", exc_info=True)
                    
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected. Session ID: {session_id}")
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for session {session_id}: {e}", exc_info=True)
    finally:
        # Perform cleanup
        try:
            summary = await orchestrator.end_session(session_id)
            logger.info(f"Session {session_id} resources released. Summary: {summary}")
        except Exception as e:
            logger.error(f"Error releasing session resources: {e}")

if __name__ == "__main__":
    import uvicorn
    # Start ASGI Server
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False  # Re-loading can cause double-initialization of whisper model
    )

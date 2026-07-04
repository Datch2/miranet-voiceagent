import asyncio
import websockets
import json
import time
import sys
import os

# Server WS address
WS_URL = "ws://localhost:8000/ws"
NUM_CONCURRENT_CALLS = 15
AUDIO_CHUNK_SIZE = 3200  # 100ms of PCM 16kHz audio
AUDIO_STREAM_LOOPS = 20  # Stream 2.0 seconds of audio

async def simulate_single_call(call_id: int):
    """
    Simulates a single customer voice call:
    1. Connects via WebSocket.
    2. Streams simulated audio chunks.
    3. Triggers 'end_of_speech' processing.
    4. Receives and measures agent response.
    """
    session_id = f"stress_session_{call_id}_{int(time.time())}"
    # Diego Torres DNI (RT000001 - Norte)
    uri = f"{WS_URL}?session_id={session_id}&login_type=DNI&login_value=12345678"
    
    start_time = time.perf_counter()
    try:
        async with websockets.connect(uri) as ws:
            # 1. Simulate streaming audio chunks (100ms each)
            dummy_pcm_chunk = bytes([0] * AUDIO_CHUNK_SIZE)
            for _ in range(AUDIO_STREAM_LOOPS):
                await ws.send(dummy_pcm_chunk)
                # Wait for real-time network feedback from server
                resp = await ws.recv()
                await asyncio.sleep(0.05)  # slight delay to simulate streaming
                
            # 2. Declare End of Speech to trigger NLP/IA processing
            end_msg = {
                "type": "end_of_speech",
                "duracion_audio": float(AUDIO_STREAM_LOOPS * 0.1)
            }
            await ws.send(json.dumps(end_msg))
            
            # 3. Wait for final agent response and metadata
            final_resp_str = await ws.recv()
            final_data = json.loads(final_resp_str)
            
            latency = (time.perf_counter() - start_time)
            
            # Extract latency measured on server
            server_latency = final_data.get("metricas_agente", {}).get("latencia_p95_ms", 0.0)
            intent = final_data.get("intent", "N/A")
            
            print(f"[Call #{call_id}] Response Received. Total RTT: {latency:.2f}s | Server Latency: {server_latency/1000:.2f}s | Intent: {intent}")
            return {
                "status": "success",
                "rtt": latency,
                "server_latency": server_latency / 1000.0,
                "intent": intent
            }
            
    except Exception as e:
        print(f"[Call #{call_id}] Connection Failed: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }

async def run_stress_test():
    print("=================================================================")
    print(f"      MIRANET VOICEAGENT - CONCURRENT LOAD TEST (HU-19)")
    print("=================================================================")
    print(f" Target URL: {WS_URL}")
    print(f" Simulating {NUM_CONCURRENT_CALLS} parallel client calls...")
    print(" Streaming audio chunks and triggering NLP analysis...")
    print("=================================================================\n")
    
    start_test = time.perf_counter()
    
    # Spawn 15 concurrent tasks
    tasks = [simulate_single_call(i) for i in range(1, NUM_CONCURRENT_CALLS + 1)]
    results = await asyncio.gather(*tasks)
    
    end_test = time.perf_counter()
    
    # Calculate statistics
    success_calls = [r for r in results if r.get("status") == "success"]
    failed_calls = [r for r in results if r.get("status") == "failed"]
    
    print("\n" + "="*60)
    print("                 📈 RESULTADOS DE LA PRUEBA")
    print("="*60)
    print(f" Total de llamadas simuladas: {NUM_CONCURRENT_CALLS}")
    print(f" Exitosas: {len(success_calls)} | Fallidas: {len(failed_calls)}")
    
    if success_calls:
        rtts = [c["rtt"] for c in success_calls]
        server_latencies = [c["server_latency"] for c in success_calls]
        
        avg_rtt = sum(rtts) / len(rtts)
        max_rtt = max(rtts)
        avg_server = sum(server_latencies) / len(server_latencies)
        max_server = max(server_latencies)
        
        print(f" Tiempo promedio de RTT (ida/vuelta): {avg_rtt:.2f} s")
        print(f" Tiempo máximo de RTT: {max_rtt:.2f} s")
        print(f" Tiempo promedio de Inferencia IA: {avg_server:.2f} s")
        print(f" Tiempo máximo de Inferencia IA: {max_server:.2f} s")
        print(f" Duración total de la prueba: {end_test - start_test:.2f} s")
    print("="*60)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_stress_test())

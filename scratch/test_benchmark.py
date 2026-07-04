import asyncio
import httpx
import time
import json
import sys

OLLAMA_URL = "http://localhost:11434/api/chat"

# 5 representative support queries from clients
TEST_SCENARIOS = [
    "Hola buenos días, quería consultar sobre mi servicio",
    "Mi internet está demasiado lento, demora mucho en cargar Netflix",
    "Se me cayó la señal por completo, tengo luz roja en el módem de fibra",
    "Quiero saber cuál es mi saldo pendiente y cuándo vence mi recibo",
    "No hay internet en toda mi cuadra, mis vecinos tampoco tienen señal"
]

SYSTEM_PROMPT = (
    "Eres el clasificador de soporte técnico de Miranet SAC.\n"
    "Analiza la queja del cliente y responde estrictamente con un objeto JSON con el siguiente formato:\n"
    "{\n"
    "  \"nivel_asignado\": \"[bajo/medio/alto/critico]\",\n"
    "  \"diagnostico_causa_raiz\": \"[Diagnóstico técnico breve]\",\n"
    "  \"porcentaje_confianza\": \"[0-100%]\",\n"
    "  \"respuesta_cliente\": \"[Mensaje de voz súper corto y conciso, máximo 20 palabras]\"\n"
    "}\n"
    "No incluyas explicaciones ni bloques de código markdown fuera del JSON."
)

async def test_model(model_name: str) -> dict:
    print(f"\n[BENCHMARK] Evaluando Modelo: '{model_name}'...")
    latencies = []
    compliance_count = 0
    client = httpx.AsyncClient(timeout=30.0)
    
    # Check if model is pulled
    try:
        # Just check list
        res = await client.post("http://localhost:11434/api/show", json={"name": model_name})
        if res.status_code != 200:
            print(f"⚠️  El modelo '{model_name}' no parece estar instalado en Ollama. Saltando...")
            await client.aclose()
            return None
    except Exception as e:
        print(f"⚠️  No se pudo conectar a Ollama: {e}")
        await client.aclose()
        return None

    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": scenario}
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2, "num_predict": 128}
        }
        
        start_time = time.perf_counter()
        try:
            response = await client.post(OLLAMA_URL, json=payload)
            latency = (time.perf_counter() - start_time) * 1000.0
            latencies.append(latency)
            
            if response.status_code == 200:
                resp_text = response.json().get("message", {}).get("content", "").strip()
                # Check JSON compliance
                try:
                    parsed = json.loads(resp_text)
                    required_keys = ["nivel_asignado", "diagnostico_causa_raiz", "porcentaje_confianza", "respuesta_cliente"]
                    if all(k in parsed for k in required_keys):
                        compliance_count += 1
                        print(f"  [Caso #{i}] OK ({latency:.0f}ms) | Intent: {parsed.get('nivel_asignado')}")
                    else:
                        print(f"  [Caso #{i}] FAILED ({latency:.0f}ms) | Llaves faltantes en JSON")
                except json.JSONDecodeError:
                    print(f"  [Caso #{i}] FAILED ({latency:.0f}ms) | No es un JSON válido")
            else:
                print(f"  [Caso #{i}] FAILED | Servidor respondió con código {response.status_code}")
        except Exception as e:
            print(f"  [Caso #{i}] ERROR: {e}")
            
    await client.aclose()
    
    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0]
        compliance_rate = (compliance_count / len(TEST_SCENARIOS)) * 100.0
        return {
            "avg_latency_ms": avg_lat,
            "p95_latency_ms": p95_lat,
            "compliance_rate": compliance_rate
        }
    return None

async def run_benchmark():
    print("=================================================================")
    print("        OLLAMA LLM BENCHMARK COMPARATIVO - MISTRAL vs PHI-3")
    print("=================================================================")
    print(" Evaluando velocidad de inferencia local y adherencia a JSON...")
    print("=================================================================\n")
    
    # 1. Test Phi-3 (default model)
    phi3_results = await test_model("phi3")
    
    # 2. Test Mistral (historical model)
    mistral_results = await test_model("mistral")
    
    # Show comparison report
    print("\n" + "="*60)
    print("             📊 REPORTE FINAL DE LA COMPARACIÓN")
    print("="*60)
    
    if phi3_results:
        print(f"  [PHI-3 MINI (3.8B)]")
        print(f"    - Latencia Promedio: {phi3_results['avg_latency_ms']:.1f} ms")
        print(f"    - Latencia p95:      {phi3_results['p95_latency_ms']:.1f} ms")
        print(f"    - Cumplimiento JSON: {phi3_results['compliance_rate']:.1f}%")
        
    if mistral_results:
        print(f"\n  [MISTRAL (7B)]")
        print(f"    - Latencia Promedio: {mistral_results['avg_latency_ms']:.1f} ms")
        print(f"    - Latencia p95:      {mistral_results['p95_latency_ms']:.1f} ms")
        print(f"    - Cumplimiento JSON: {mistral_results['compliance_rate']:.1f}%")
        
    if phi3_results and mistral_results:
        diff = mistral_results['avg_latency_ms'] / phi3_results['avg_latency_ms']
        print("\n" + "-"*60)
        print(f"  🏆 CONCLUSIÓN: Phi-3 es {diff:.1fx} veces más rápido que Mistral.")
    print("="*60)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_benchmark())

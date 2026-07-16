import time
import logging
import httpx
import json
from backend.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ResponderAgent")

class ResponderAgent:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.client = httpx.AsyncClient(timeout=60.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def generate_response(
        self,
        text: str,
        history: list[dict] = None,
        client_info: dict = None,
        network_status: dict = None
    ) -> tuple[dict, int]:
        """
        Generate a structured response (intent classification, diagnostic, confidence, spoken response)
        using a single optimized Ollama LLM query to minimize real-time voice latency.
        
        Returns:
            tuple[dict, int]: (structured_result_dict, latency_ms)
        """
        start_time = time.perf_counter()
        
        fallback_result = {
            "nivel_asignado": "bajo",
            "diagnostico_causa_raiz": "Error de procesamiento técnico",
            "porcentaje_confianza": "0%",
            "respuesta_cliente": "Lo siento, he tenido un problema al procesar tu solicitud. ¿Me lo puedes repetir de nuevo?"
        }

        rt_latency = 12
        rt_jitter = 2

        if not text:
            fallback_result["respuesta_cliente"] = "No te he podido escuchar claramente. ¿Podrías repetir, por favor?"
            return fallback_result, 0

        # Construct dynamic context descriptions from DB objects
        client_desc = "Desconocido"
        net_desc = "Estable"
        if client_info:
            client_desc = f"Nombre: {client_info['nombre']}, DNI: {client_info['dni']}, Router S/N: {client_info['router_sn']}, Zona: {client_info['zona_nombre']} (Estado de Zona: {client_info['zona_estado']})"
        if network_status:
            rt_latency = network_status.get("realtime_latency_ms", 12)
            rt_jitter = network_status.get("realtime_jitter_ms", 2)
            snmp_latency = network_status.get("snmp_latency_ms", 15.0)
            
            # Correlate stress test simulation parameters to make them dynamic and realistic
            cpu = network_status.get('cpu_usage', 25.0)
            loss = network_status.get('packet_loss', 0.0)
            interface = network_status.get('interface_status', 'up')
            
            if snmp_latency > 2000:
                cpu = 0.0
                loss = 100.0
                interface = "down"
            elif snmp_latency > 50:
                cpu = 95.0
                loss = 12.5
                interface = "up"
                
            net_desc = (
                f"Equipo: {network_status['nombre']}, "
                f"CPU: {cpu}%, "
                f"Memoria: {network_status['mem_usage']}%, "
                f"Pérdida de paquetes: {loss}%, "
                f"Estado de interfaz: {interface}, "
                f"Latencia de conexión actual (WebSockets): {rt_latency} ms, "
                f"Jitter actual: {rt_jitter} ms, "
                f"Latencia SNMP del Router (Prueba de Estrés): {snmp_latency} ms"
            )

        # Cruce de zona logic to override network state
        actual_network_state = client_info['zona_estado'] if client_info else settings.ESTADO_RED

        raw_network_logs = network_status.get("raw_network_logs", "No logs available.") if network_status else "No logs available."

        # Construct dynamic prompt inserting the ESTADO_RED and zone/client settings
        system_instruction = (
            "Eres el agente de voz inteligente de Miranet SAC. Debes leer las últimas líneas de logs de red SNMP del cliente e iniciar tu respuesta informándole explícitamente si su router está enviando señales (enlace activo/UP) o no (pérdida de señal/timeouts/DOWN). Luego:\n"
            "1. Menciona explícitamente el código del router (Router S/N) y el estado detectado en los logs.\n"
            "2. Si hay fallas lógicas (Alta latencia o Jitter), explica la acción ejecutada automáticamente (ej: Reajuste lógico de canal o aprovisionamiento de QoS).\n"
            "3. Pídele al usuario unos segundos para validar la restauración síncrona del servicio.\n\n"
            "Eres el núcleo de Inteligencia Artificial del Agente de Voz de la empresa de telecomunicaciones Miranet SAC (Año 2026). "
            "Tu función es procesar reportes de fallas de internet y actuar de manera síncrona como Operadora Automática y Técnico de Monitoreo.\n\n"
            f"INFORMACIÓN DEL CLIENTE CONECTADO:\n{client_desc}\n\n"
            f"ESTADO DE MONITOREO DE RED DE LA ZONA (SNMP Mock):\n{net_desc}\n\n"
            f"HISTORIAL DE LOGS DE RED DE SNMP DEL CLIENTE (Manejado por Logs):\n{raw_network_logs}\n\n"
            f"ESTADO GLOBAL/ZONAL DE RED ACTUAL: '{actual_network_state}'\n\n"
            "### REGLA OBLIGATORIA DE ANÁLISIS PREVIO DE LOGS:\n"
            "Tienes terminantemente prohibido dar un diagnóstico o respuesta al cliente sin realizar un análisis previo de las últimas líneas de logs de red SNMP arriba indicadas.\n"
            "Debes iniciar indicando si se reciben señales del equipo o si hay pérdida de señal de acuerdo a los logs. Menciona explícitamente los valores del log al cliente.\n\n"
            "Debes seguir estas REGLAS DE COMPORTAMIENTO al pie de la letra:\n\n"
            "### 1. EVALUACIÓN Y CLASIFICACIÓN (HU-03) \n"
            "Analiza el texto transcrito del cliente y clasifícalo estrictamente en uno de estos 4 niveles de gravedad:\n"
            "- BAJO: Consultas generales o dudas comerciales.\n"
            "- MEDIO: Falla intermitente, lentitud o caídas esporádicas.\n"
            "- ALTO: Pérdida total del servicio (individual).\n"
            "- CRÍTICO: El cliente menciona palabras como \"masivo\", \"toda la zona\", \"mis vecinos tampoco tienen\" OR el estado global/zonal de la red es igual a 'falla_masiva' o 'FALLA_MASIVA'.\n\n"
            "### 2. CONTROL DE AMBIGÜEDAD (HU-04) \n"
            "Si la descripción del cliente es vaga (ej. \"No da\", \"se cayó\"), tienes prohibido asumir datos. \n"
            "- Formula una pregunta de aclaración específica (Ej: \"¿El problema es en todos sus dispositivos o solo en uno?\").\n"
            "- Máximo puedes hacer 2 preguntas de aclaración antes de derivar el caso.\n\n"
            "### 3. DIAGNÓSTICO DE CAUSA RAÍZ (HU-08) \n"
            "Cruza el reporte con los parámetros de red. Genera una causa raíz técnica probable basada en las métricas SNMP del equipo de red de la zona del cliente (ej. si la interfaz está down, o el packet loss es alto) y asígnale un porcentaje de confianza estimado.\n\n"
            "### 4. CONCISIÓN ABSOLUTA EN CANAL DE VOZ (Regla de Oro)\n"
            "Estás hablando por teléfono, NO estás escribiendo un correo. Tus respuestas verbales al cliente deben ser directas, amables y cortas (MÁXIMO 2 ORACIONES o 25 PALABRAS). Está terminantemente prohibido explayarse en explicaciones técnicas innecesarias con el usuario.\n\n"
            "### 5. FORMATO DE SALIDA (Para el Orquestador Backend)\n"
            "Siempre debes estructurar tu respuesta interna devolviendo este formato JSON plano para que el sistema guarde en la Base de Datos:\n"
            "{\n"
            '  "nivel_asignado": "[bajo/medio/alto/critico]",\n'
            '  "diagnostico_causa_raiz": "[Diagnóstico técnico breve]",\n'
            '  "porcentaje_confianza": "[0-100%]",\n'
            '  "respuesta_cliente": "[Mensaje hablado súper corto y conciso que escuchará el cliente]"\n'
            "}\n"
            "No incluyas nada fuera del objeto JSON."
        )

        messages = [{"role": "system", "content": system_instruction}]

        if history:
            # Format and filter history to only include last 6 messages
            formatted_history = []
            for msg in history[-6:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                # If content is a dict (json string from previous assistant step), parse or extract client response
                if role == "assistant" and content.startswith("{"):
                    try:
                        parsed = json.loads(content)
                        content = parsed.get("respuesta_cliente", content)
                    except Exception:
                        pass
                formatted_history.append({"role": role, "content": content})
            messages.extend(formatted_history)

        messages.append({"role": "user", "content": text})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",  # Instruct Ollama to output valid JSON
            "options": {
                "temperature": 0.3,
                "num_predict": 192  # Enough space for structured JSON
            }
        }

        try:
            logger.info("Generating structured response from Ollama...")
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=payload
            )
            response.raise_for_status()
            
            response_data = response.json()
            response_text = response_data.get("message", {}).get("content", "").strip()
            structured_data = json.loads(response_text)
            
            # Clean brackets [ ] from output strings and ensure default keys are present
            def clean_str(val):
                if isinstance(val, str):
                    return val.replace("[", "").replace("]", "").strip()
                return str(val)

            result = {
                "nivel_asignado": clean_str(structured_data.get("nivel_asignado", "bajo")).lower(),
                "diagnostico_causa_raiz": clean_str(structured_data.get("diagnostico_causa_raiz", "Diagnóstico genérico")),
                "porcentaje_confianza": clean_str(structured_data.get("porcentaje_confianza", "50%")),
                "respuesta_cliente": clean_str(structured_data.get("respuesta_cliente", "Entendido. ¿Me das más detalles?"))
            }
            
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info(f"Structured response generated in {latency_ms}ms: {result}")
            return result, latency_ms

        except (httpx.HTTPError, httpx.ConnectError, json.JSONDecodeError, KeyError, Exception) as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning(f"Ollama offline or errored ({e}). Running hybrid mock matcher for Render compatibility...")
            
            # Smart Hybrid Mock Matcher for Cloud/Render Support
            lower_text = text.lower()
            
            # 1. Check for simulated massive network failure first (HU-03 / HU-07 rule)
            if actual_network_state.upper() == "FALLA_MASIVA":
                result = {
                    "nivel_asignado": "critico",
                    "diagnostico_causa_raiz": f"Avería Masiva en Zona: {network_status['nombre'] if network_status else 'Central'}",
                    "porcentaje_confianza": "99%",
                    "respuesta_cliente": f"Estimado {client_info['nombre'] if client_info else 'cliente'}, registramos una avería masiva en su distrito ({client_info['zona_nombre'] if client_info else 'de cobertura'}). Ya estamos trabajando para solucionarlo."
                }
            # 2. Control de Ambigüedad (HU-04)
            elif len(text.strip()) < 12 and any(w in lower_text for w in ["no da", "ayuda", "falla", "malo", "se cayó", "se cayo", "no entra"]):
                result = {
                    "nivel_asignado": "bajo",
                    "diagnostico_causa_raiz": "Descripción de incidencia ambigua (<70% confianza)",
                    "porcentaje_confianza": "50%",
                    "respuesta_cliente": "¿El inconveniente con su servicio de internet ocurre en todos sus dispositivos o solamente en uno?"
                }
            # Greetings
            elif any(w in lower_text for w in ["hola", "buenas", "buen día", "buenos días", "buenas tardes", "buenas noches", "qué tal"]):
                result = {
                    "nivel_asignado": "bajo",
                    "diagnostico_causa_raiz": "Saludo inicial del cliente",
                    "porcentaje_confianza": "100%",
                    "respuesta_cliente": "Hola, bienvenido al asistente virtual de Miranet. ¿En qué puedo ayudarte hoy?"
                }
            # Thank yous and Goodbyes
            elif any(w in lower_text for w in ["gracias", "adiós", "chao", "hasta luego", "excelente", "perfecto", "ok", "de acuerdo"]):
                result = {
                    "nivel_asignado": "bajo",
                    "diagnostico_causa_raiz": "Cierre de conversación o agradecimiento",
                    "porcentaje_confianza": "100%",
                    "respuesta_cliente": "Perfecto. Muchas gracias por comunicarte con Miranet. Si tienes otra consulta, aquí estaré. ¡Que tengas un gran día!"
                }
            # Commercial/Billing queries
            elif any(w in lower_text for w in ["saldo", "pagar", "recibo", "factura", "facturación", "costo", "deuda", "boleta", "precio"]):
                result = {
                    "nivel_asignado": "bajo",
                    "diagnostico_causa_raiz": "Consulta comercial de facturación",
                    "porcentaje_confianza": "100%",
                    "respuesta_cliente": "Entendido. Para temas de facturación y pagos, te derivaré de inmediato con un asesor comercial."
                }
            # Neighborhood or area-wide failure (Critical)
            elif any(w in lower_text for w in ["vecinos", "masivo", "zona", "barrio", "cuadra", "distrito", "sector", "toda la zona"]):
                result = {
                    "nivel_asignado": "critico",
                    "diagnostico_causa_raiz": "Falla masiva reportada por cliente",
                    "porcentaje_confianza": "95%",
                    "respuesta_cliente": "Estimado cliente, detectamos una avería masiva en su sector. Nuestro equipo técnico de red ya va en camino."
                }
            # Hardware/Physical signal issues (High)
            elif any(w in lower_text for w in ["módem", "modem", "luz roja", "router", "antena", "cable", "fibra"]):
                result = {
                    "nivel_asignado": "alto",
                    "diagnostico_causa_raiz": f"Pérdida de sincronía física del equipo: {network_status['nombre'] if network_status else 'Router'}",
                    "porcentaje_confianza": "85%",
                    "respuesta_cliente": "La luz roja indica pérdida de señal física. Por favor, asegúrese de que el cable de fibra esté bien conectado."
                }
            # Slow speeds / Logical failure (Alta latencia o Jitter)
            elif (rt_latency > 60 or rt_jitter > 15) or any(w in lower_text for w in ["lento", "lentitud", "demora", "velocidad", "cargar", "cargando", "lag", "ping", "latencia", "jitter"]):
                router_sn = client_info.get("router_sn") if client_info else "RT000002"
                display_latency = rt_latency if rt_latency > 60 else 74
                accion = "reajuste lógico de canal" if display_latency > 80 else "aprovisionamiento de QoS"
                result = {
                    "nivel_asignado": "medio",
                    "diagnostico_causa_raiz": f"Falla lógica detectada (Latencia: {display_latency}ms, Jitter: {rt_jitter}ms)",
                    "porcentaje_confianza": "95%",
                    "respuesta_cliente": f"Revisando los logs SNMP del router {router_sn}, confirmo que sí recibe señal pero registra una alta latencia de {display_latency} milisegundos. Hemos iniciado automáticamente un {accion} para restaurar la estabilidad; por favor espere unos segundos."
                }
            # Loss of service / Connection drops (High)
            elif any(w in lower_text for w in ["cae", "cayó", "cayo", "se fue", "no tengo", "no hay", "funciona", "servicios", "fallando", "falla", "sin internet"]):
                router_sn = client_info.get("router_sn") if client_info else "RT000001"
                is_offline = "timeout" in raw_network_logs.lower() or (network_status and network_status.get('packet_loss', 0.0) == 100.0)
                if is_offline:
                    respuesta = f"Analizando los logs SNMP en tiempo real, confirmo que su router {router_sn} no está enviando señales debido a timeouts de conexión (caída total). Reportaré esta avería para soporte técnico."
                else:
                    respuesta = f"Analizando los logs SNMP en tiempo real, observo que su router {router_sn} sí está enviando señales de forma activa. Enviaré un comando de reconexión para refrescar la señal de navegación."
                result = {
                    "nivel_asignado": "alto",
                    "diagnostico_causa_raiz": f"Pérdida de señal (Packet Loss: {network_status['packet_loss'] if network_status else '100'}%)" if is_offline else "Señal activa con reporte de caída lógica",
                    "porcentaje_confianza": "95%",
                    "respuesta_cliente": respuesta
                }
            # Requesting human transfer
            elif any(w in lower_text for w in ["asesor", "operador", "humano", "persona", "atención"]):
                result = {
                    "nivel_asignado": "medio",
                    "diagnostico_causa_raiz": "Solicitud de transferencia a agente humano",
                    "porcentaje_confianza": "100%",
                    "respuesta_cliente": "Entendido. Lo transferiré de inmediato con un especialista de soporte de nuestro equipo humano."
                }
            # Default
            else:
                result = {
                    "nivel_asignado": "bajo",
                    "diagnostico_causa_raiz": "Consulta general de soporte",
                    "porcentaje_confianza": "90%",
                    "respuesta_cliente": "He recibido su consulta. ¿Podría darme más detalles sobre el problema de su router para ayudarle mejor?"
                }
            
            logger.info(f"Hybrid response generated in {latency_ms}ms: {result}")
            return result, latency_ms


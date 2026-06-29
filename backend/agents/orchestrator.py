import logging
from backend.db.database import db
from backend.agents.transcriber import TranscriberAgent
from backend.agents.classifier import ClassifierAgent
from backend.agents.responder import ResponderAgent
from backend.agents.network_monitor import NetworkMonitorAgent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OrchestratorAgent")

class OrchestratorAgent:
    def __init__(
        self,
        transcriber: TranscriberAgent,
        classifier: ClassifierAgent,
        responder: ResponderAgent
    ):
        self.transcriber = transcriber
        self.classifier = classifier
        self.responder = responder
        # Store active session contexts in memory
        self.active_sessions = {}

    async def start_session(
        self, 
        session_id: str, 
        login_type: str | None = None, 
        login_value: str | None = None
    ):
        """Initialize resources and database records for a new session."""
        logger.info(f"Starting session: {session_id} (Login: {login_type}={login_value})")
        
        # Log to DB
        await db.create_conversation(session_id)
        
        # Fetch client info from local database using identifier
        client_info = None
        if login_type and login_value:
            client_info = await db.get_client_by_identifier(login_type, login_value)
            
        # Fallback default client if lookup yields nothing
        if not client_info:
            logger.info("Client details not found or not provided, loading default customer session.")
            client_info = {
                "id": 2,
                "nombre": "Sergio Perez (Consulta General)",
                "dni": "87654321",
                "router_sn": "RT000002",
                "zona_id": 2,
                "zona_nombre": "Sur",
                "zona_estado": "operativo"
            }
            
        # Fetch network status parameters for the zone
        network_status = await db.get_network_status_by_zone(client_info["zona_id"])
        
        # Setup session context
        self.active_sessions[session_id] = {
            "audio_buffer": bytearray(),
            "sequence_counter": 0,
            "history": [],
            "network_monitor": NetworkMonitorAgent(),
            "client_info": client_info,
            "network_status": network_status
        }

    async def append_audio_chunk(
        self,
        session_id: str,
        chunk: bytes,
        sequence_id: int | None = None
    ) -> dict:
        """
        Append incoming raw audio bytes to the session buffer.
        
        Returns:
            dict: Real-time network streaming diagnostics
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise RuntimeError(f"Session {session_id} is not initialized.")

        # Append to buffer
        session["audio_buffer"].extend(chunk)

        # Log network packet to compute jitter/loss/bandwidth
        net_monitor: NetworkMonitorAgent = session["network_monitor"]
        metrics = net_monitor.record_packet(len(chunk), sequence_id)
        
        return metrics

    async def process_audio_segment(self, session_id: str) -> dict:
        """
        Trigger the processing cascade:
        1. Whisper transcription of accumulated audio.
        2. Ollama intent & sentiment classification (with client/network parameters).
        3. DB persistence (incidents & técnico reports).
        
        Returns:
            dict: The complete voice transaction metadata and response text.
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise RuntimeError(f"Session {session_id} is not initialized.")

        audio_bytes = bytes(session["audio_buffer"])
        
        # Reset the audio buffer immediately to prepare for the next user utterance
        session["audio_buffer"] = bytearray()
        
        if not audio_bytes or len(audio_bytes) < 3200:  # less than 100ms of audio
            return {
                "transcription": "",
                "response": "No he recibido suficiente audio. ¿Podrías hablar más fuerte?",
                "intent": "unknown",
                "sentiment": "neutral",
                "latencies": {"transcription": 0, "classification": 0, "responder": 0}
            }

        # Increment sequence counter for this session
        session["sequence_counter"] += 1
        sequence_num = session["sequence_counter"]

        logger.info(f"Processing audio segment for {session_id} (seq: {sequence_num}, size: {len(audio_bytes)} bytes)")

        # 1. Transcribe
        transcription, t_latency = await self.transcriber.transcribe(audio_bytes)
        
        if not transcription.strip():
            logger.info("Transcription returned empty text.")
            return {
                "transcription": "",
                "response": "No te he escuchado. ¿Podrías repetir?",
                "intent": "unknown",
                "sentiment": "neutral",
                "latencies": {"transcription": t_latency, "classification": 0, "responder": 0}
            }

        # 2. Classify & Respond using active context variables
        c_latency = 0
        client_info = session.get("client_info")
        network_status = session.get("network_status")
        
        # Enrich network_status with real-time connection telemetry from network_monitor
        net_monitor = session["network_monitor"]
        rt_latency = 12
        if net_monitor.packet_intervals:
            rt_latency = int(sum(net_monitor.packet_intervals) / len(net_monitor.packet_intervals))
        
        rt_jitter = 2
        if len(net_monitor.packet_intervals) > 1:
            rt_jitter = int(abs(net_monitor.packet_intervals[-1] - net_monitor.packet_intervals[-2]))
            
        enriched_network_status = dict(network_status) if network_status else {}
        enriched_network_status["realtime_latency_ms"] = rt_latency
        enriched_network_status["realtime_jitter_ms"] = rt_jitter

        result_json, r_latency = await self.responder.generate_response(
            text=transcription,
            history=session["history"],
            client_info=client_info,
            network_status=enriched_network_status
        )
        
        intent = result_json.get("nivel_asignado", "bajo")
        diagnostico = result_json.get("diagnostico_causa_raiz", "Problema general")
        confianza_str = result_json.get("porcentaje_confianza", "90%").replace("%", "")
        try:
            confianza = float(confianza_str)
        except ValueError:
            confianza = 90.0
            
        sentiment = f"{diagnostico} ({confianza_str}%)"
        response = result_json.get("respuesta_cliente", "...")

        # Update Session History
        session["history"].append({"role": "user", "content": transcription})
        session["history"].append({"role": "assistant", "content": response})

        # 4. Save to Database: Log voice interaction
        await db.log_voice_interaction(
            session_id=session_id,
            sequence_number=sequence_num,
            audio_size_bytes=len(audio_bytes),
            transcription=transcription,
            classification_intent=intent,
            classification_sentiment=sentiment,
            response_text=response,
            transcription_latency_ms=t_latency,
            classification_latency_ms=c_latency,
            response_latency_ms=r_latency
        )

        # Save Incident & Technical Report (HU-10 / HU-12)
        import json
        detalles_json = json.dumps({
            "client_name": client_info.get("nombre") if client_info else "N/A",
            "dni": client_info.get("dni") if client_info else "N/A",
            "router_sn": client_info.get("router_sn") if client_info else "N/A",
            "zone": client_info.get("zona_nombre") if client_info else "N/A",
            "network_status": network_status
        })
        await db.create_incident_and_report(
            session_id=session_id,
            cliente_id=client_info.get("id") if client_info else 2,
            descripcion=transcription,
            nivel_gravedad=intent,
            estado="diagnosticando",
            diagnostico=diagnostico,
            confianza=confianza,
            detalles_tecnicos=detalles_json
        )

        # Log current network summary stats to database
        net_monitor: NetworkMonitorAgent = session["network_monitor"]
        summary = net_monitor.get_summary()
        await db.log_network_metrics(
            session_id=session_id,
            latency_ms=int(summary["avg_jitter_ms"]),  # average jitter as nominal network lag
            packet_loss_rate=summary["packet_loss_rate"],
            jitter_ms=int(summary["avg_jitter_ms"]),
            bandwidth_kbps=summary["avg_bandwidth_kbps"]
        )

        # Trigger active remediation and update cached connection parameters
        await self._handle_remediation_and_update_status(session, intent, transcription)

        return {
            "transcription": transcription,
            "response": response,
            "intent": intent,
            "sentiment": sentiment,
            "latencies": {
                "transcription": t_latency,
                "classification": c_latency,
                "responder": r_latency
            },
            "client_info": client_info,
            "network_status": session["network_status"],
            "diagnostico_causa_raiz": diagnostico,
            "porcentaje_confianza": f"{confianza_str}%"
        }

    async def process_text_segment(self, session_id: str, transcription: str) -> dict:
        """
        Process a text transcription sent directly from the client (browser speech recognition).
        Bypasses local Whisper to save memory and CPU.
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise RuntimeError(f"Session {session_id} is not initialized.")

        audio_bytes = bytes(session["audio_buffer"])
        # Clear buffer
        session["audio_buffer"] = bytearray()
        
        # Audio size is either the buffer size or default 16000 bytes
        audio_size = len(audio_bytes) if audio_bytes else 16000
        
        # Increment sequence counter
        session["sequence_counter"] += 1
        sequence_num = session["sequence_counter"]

        logger.info(f"Processing text segment for {session_id} (seq: {sequence_num}, text: '{transcription}')")

        t_latency = 0
        c_latency = 0

        # Respond (Ollama or Hybrid Matcher)
        client_info = session.get("client_info")
        network_status = session.get("network_status")
        
        # Enrich network_status with real-time connection telemetry from network_monitor
        net_monitor = session["network_monitor"]
        rt_latency = 12
        if net_monitor.packet_intervals:
            rt_latency = int(sum(net_monitor.packet_intervals) / len(net_monitor.packet_intervals))
        
        rt_jitter = 2
        if len(net_monitor.packet_intervals) > 1:
            rt_jitter = int(abs(net_monitor.packet_intervals[-1] - net_monitor.packet_intervals[-2]))
            
        enriched_network_status = dict(network_status) if network_status else {}
        enriched_network_status["realtime_latency_ms"] = rt_latency
        enriched_network_status["realtime_jitter_ms"] = rt_jitter

        result_json, r_latency = await self.responder.generate_response(
            text=transcription,
            history=session["history"],
            client_info=client_info,
            network_status=enriched_network_status
        )
        
        intent = result_json.get("nivel_asignado", "bajo")
        diagnostico = result_json.get("diagnostico_causa_raiz", "Problema general")
        confianza_str = result_json.get("porcentaje_confianza", "90%").replace("%", "")
        try:
            confianza = float(confianza_str)
        except ValueError:
            confianza = 90.0
            
        sentiment = f"{diagnostico} ({confianza_str}%)"
        response = result_json.get("respuesta_cliente", "...")

        # Update Session History
        session["history"].append({"role": "user", "content": transcription})
        session["history"].append({"role": "assistant", "content": response})

        # Save to Database asynchronously
        await db.log_voice_interaction(
            session_id=session_id,
            sequence_number=sequence_num,
            audio_size_bytes=audio_size,
            transcription=transcription,
            classification_intent=intent,
            classification_sentiment=sentiment,
            response_text=response,
            transcription_latency_ms=t_latency,
            classification_latency_ms=c_latency,
            response_latency_ms=r_latency
        )

        # Save Incident & Technical Report (HU-10 / HU-12)
        import json
        detalles_json = json.dumps({
            "client_name": client_info.get("nombre") if client_info else "N/A",
            "dni": client_info.get("dni") if client_info else "N/A",
            "router_sn": client_info.get("router_sn") if client_info else "N/A",
            "zone": client_info.get("zona_nombre") if client_info else "N/A",
            "network_status": network_status
        })
        await db.create_incident_and_report(
            session_id=session_id,
            cliente_id=client_info.get("id") if client_info else 2,
            descripcion=transcription,
            nivel_gravedad=intent,
            estado="diagnosticando",
            diagnostico=diagnostico,
            confianza=confianza,
            detalles_tecnicos=detalles_json
        )

        # Log current network summary stats to database
        net_monitor: NetworkMonitorAgent = session["network_monitor"]
        summary = net_monitor.get_summary()
        await db.log_network_metrics(
            session_id=session_id,
            latency_ms=int(summary["avg_jitter_ms"]),
            packet_loss_rate=summary["packet_loss_rate"],
            jitter_ms=int(summary["avg_jitter_ms"]),
            bandwidth_kbps=summary["avg_bandwidth_kbps"]
        )

        # Trigger active remediation and update cached connection parameters
        await self._handle_remediation_and_update_status(session, intent, transcription)

        return {
            "transcription": transcription,
            "response": response,
            "intent": intent,
            "sentiment": sentiment,
            "latencies": {
                "transcription": t_latency,
                "classification": c_latency,
                "responder": r_latency
            },
            "client_info": client_info,
            "network_status": session["network_status"],
            "diagnostico_causa_raiz": diagnostico,
            "porcentaje_confianza": f"{confianza_str}%"
        }


    async def end_session(self, session_id: str) -> dict:
        """Log final network diagnostics and release session context."""
        session = self.active_sessions.pop(session_id, None)
        if not session:
            return {}

        net_monitor: NetworkMonitorAgent = session["network_monitor"]
        summary = net_monitor.get_summary()
        logger.info(f"Session {session_id} ended. Final network summary: {summary}")
        
        return summary

    async def _handle_remediation_and_update_status(
        self,
        session: dict,
        intent: str,
        transcription: str
    ):
        """
        Executes active remediation steps asynchronously based on intent gravity 
        and updates the cached session network status.
        """
        from backend.utils.remediation import RemediationController
        
        client_info = session.get("client_info")
        network_status = session.get("network_status")
        
        if not client_info:
            return
            
        router_sn = client_info.get("router_sn", "RT000002")
        client_name = client_info.get("nombre", "Sergio Perez")
        
        # 1. Always run a live ping troubleshooting diagnostic
        await RemediationController.run_ping()
        
        # 2. Trigger remediation steps based on classified gravity
        if intent.lower() == "medio":
            # Logical network degradation -> Apply QoS Profile and Flush DNS
            logger.info(f"[Remediation Hook] Logical slowness detected. Re-provisioning QoS profile for {router_sn}...")
            await RemediationController.apply_qos_profile(router_sn, profile_speed_mbps=150)
            await RemediationController.flush_dns()
            
        elif intent.lower() == "alto":
            # Individual total outage
            interface_status = network_status.get("interface_status") if network_status else "up"
            if interface_status.lower() == "down":
                # Logical interface down -> Trigger interface flap sequence
                logger.info(f"[Remediation Hook] Interface DOWN detected for {router_sn}. Initiating reset flapping...")
                await RemediationController.reset_wan_interface(router_sn)
            else:
                # Physical outage -> Escalate support ticket
                logger.info(f"[Remediation Hook] Physical outage detected for {router_sn}. Escalating to field technician...")
                await RemediationController.send_escalation_webhook(1234, client_name, transcription)
                
        elif intent.lower() == "critico":
            # Zonal/mass critical issue -> Trigger automatic failover routing
            logger.info(f"[Remediation Hook] Critical mass outage. Triggering backup failover routing for {router_sn}...")
            await RemediationController.trigger_failover(router_sn)
            
        # 3. Pull fresh network status parameters from DB to reflect the new state in the current session
        fresh_status = await db.get_network_status_by_zone(client_info["zona_id"])
        if fresh_status:
            session["network_status"] = fresh_status
            logger.info(f"[Remediation Hook] Updated cached session network_status: {fresh_status}")

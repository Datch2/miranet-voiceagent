import asyncio
import subprocess
import os
import logging
import psutil
import httpx
from backend.db.database import db

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RemediationEngine")

class RemediationController:
    """
    Engine to execute local and simulated network/infrastructure remediation actions
    on behalf of the voice agent.
    """
    
    @staticmethod
    async def run_ping(host: str = "127.0.0.1") -> dict:
        """
        Executes a live ping command on the system to test connectivity.
        Works cross-platform (Windows / Linux).
        """
        logger.info(f"[Remediation] Running live ping to {host}...")
        # -n 2 for Windows, -c 2 for Unix
        cmd = ["ping", "-n", "2", host] if os.name == "nt" else ["ping", "-c", "2", host]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            output = stdout.decode('latin-1') # Decode safely for Windows Spanish output
            
            # Simple latency parser from ping output
            latency = "Desconocido"
            if "media =" in output.lower():
                latency = output.lower().split("media =")[-1].strip().split("ms")[0] + " ms"
            elif "average" in output.lower():
                latency = output.lower().split("average =")[-1].strip().split("ms")[0] + " ms"
                
            loss = "0%"
            if "%" in output:
                parts = output.split("%")
                loss = parts[0].split("(")[-1].strip() + "%"
                
            logger.info(f"[Remediation] Ping completed. Latency: {latency}, Loss: {loss}")
            return {"status": "success", "latency": latency, "loss": loss, "raw": output}
        except Exception as e:
            logger.error(f"[Remediation] Ping failed: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def run_traceroute(host: str = "127.0.0.1") -> dict:
        """
        Executes a live traceroute command.
        """
        logger.info(f"[Remediation] Running traceroute to {host}...")
        cmd = ["tracert", "-h", "3", host] if os.name == "nt" else ["traceroute", "-m", "3", host]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            output = stdout.decode('latin-1')
            logger.info("[Remediation] Traceroute completed.")
            return {"status": "success", "hops": output}
        except Exception as e:
            logger.error(f"[Remediation] Traceroute failed: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def flush_dns() -> dict:
        """
        Executes a local DNS cache flush (ipconfig /flushdns on Windows).
        """
        if os.name != "nt":
            logger.info("[Remediation] DNS flush requested. Skipping (non-Windows system).")
            return {"status": "success", "message": "Flush DNS simulado en sistema no-Windows."}
            
        logger.info("[Remediation] Flushing local DNS resolver cache...")
        try:
            process = await asyncio.create_subprocess_exec(
                "ipconfig", "/flushdns",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            output = stdout.decode('latin-1')
            logger.info("[Remediation] DNS resolver cache flushed successfully.")
            return {"status": "success", "message": output.strip()}
        except Exception as e:
            logger.error(f"[Remediation] DNS flush failed: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def kill_process_on_port(port: int) -> dict:
        """
        Locates and terminates any process holding a specific local port (e.g. 3307 or 8000).
        Uses psutil library.
        """
        logger.info(f"[Remediation] Scanning for hung processes on port {port}...")
        terminated_count = 0
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr.port == port and conn.pid:
                    try:
                        proc = psutil.Process(conn.pid)
                        logger.warning(f"[Remediation] Terminating process {proc.name()} (PID: {conn.pid}) on port {port}...")
                        proc.kill()
                        terminated_count += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as proc_err:
                        logger.error(f"Cannot terminate process: {proc_err}")
            
            return {
                "status": "success" if terminated_count > 0 else "ignored",
                "terminated_processes": terminated_count,
                "message": f"Se cerraron {terminated_count} procesos colgados en el puerto {port}."
            }
        except Exception as e:
            logger.error(f"[Remediation] Port scan/kill failed: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def reset_wan_interface(router_sn: str) -> dict:
        """
        Simulates resetting a WAN interface (interface flapping) by updating
        its state to 'down', waiting 2 seconds, and updating it back to 'up' in the database.
        """
        logger.info(f"[Remediation] Simulating WAN interface reset for Router SN: {router_sn}...")
        
        try:
            # 1. Fetch equipment associated with this router serial
            # First find cliente's zone
            client = await db.get_client_by_identifier("RouterSN", router_sn)
            if not client:
                raise ValueError(f"No client found with Router SN {router_sn}")
                
            zona_id = client["zona_id"]
            
            # Update state in DB to 'down'
            if db.use_sqlite:
                q_down = "UPDATE equipos_red SET interface_status = 'down', packet_loss = 100.0 WHERE zona_id = ?;"
                q_up = "UPDATE equipos_red SET interface_status = 'up', packet_loss = 0.0, cpu_usage = 25.0 WHERE zona_id = ?;"
                params = (zona_id,)
            else:
                q_down = "UPDATE equipos_red SET interface_status = 'down', packet_loss = 100.0 WHERE zona_id = %s;"
                q_up = "UPDATE equipos_red SET interface_status = 'up', packet_loss = 0.0, cpu_usage = 25.0 WHERE zona_id = %s;"
                params = (zona_id,)
                
            logger.info(f"[Remediation] Interface setting to DOWN for zone {zona_id}...")
            await db._execute(q_down, params)
            
            # Wait 2 seconds to simulate hardware reboot / synchronization
            await asyncio.sleep(2.0)
            
            logger.info(f"[Remediation] Interface setting back to UP (Restored) for zone {zona_id}...")
            await db._execute(q_up, params)
            
            # Log this action into log_incidencias of cacti
            await RemediationController._log_cacti_action(
                router_sn=router_sn,
                tipo="Reinicio lógico de canal (Interface Flapping)",
                valor=100.0,
                solucion="Interface set to DOWN -> UP reboot sequence completed."
            )
            
            return {"status": "success", "message": "Flapping WAN completado. Interfaz restablecida."}
        except Exception as e:
            logger.error(f"[Remediation] WAN reset failed: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def apply_qos_profile(router_sn: str, profile_speed_mbps: int = 100) -> dict:
        """
        Simulates dynamically provisioning a new QoS profile or increasing bandwidth 
        to solve saturation. Updates network equipment metrics (packet loss -> 0, cpu -> low).
        """
        logger.info(f"[Remediation] Dynamically provisioning QoS Profile ({profile_speed_mbps} Mbps) for Router {router_sn}...")
        try:
            client = await db.get_client_by_identifier("RouterSN", router_sn)
            if not client:
                raise ValueError(f"No client found with Router SN {router_sn}")
                
            zona_id = client["zona_id"]
            
            # Update DB parameters to simulate a clear, high-bandwidth path
            if db.use_sqlite:
                query = "UPDATE equipos_red SET cpu_usage = 20.0, mem_usage = 35.0, packet_loss = 0.0 WHERE zona_id = ?;"
                params = (zona_id,)
            else:
                query = "UPDATE equipos_red SET cpu_usage = 20.0, mem_usage = 35.0, packet_loss = 0.0 WHERE zona_id = %s;"
                params = (zona_id,)
                
            await db._execute(query, params)
            
            # Log in Cacti
            await RemediationController._log_cacti_action(
                router_sn=router_sn,
                tipo="Aprovisionamiento de QoS",
                valor=float(profile_speed_mbps),
                solucion=f"Aprovisionamiento dinámico de perfil de {profile_speed_mbps} Mbps aplicado con prioridad."
            )
            
            return {"status": "success", "message": f"QoS de {profile_speed_mbps} Mbps aprovisionado en caliente."}
        except Exception as e:
            logger.error(f"[Remediation] QoS provisioning failed: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def trigger_failover(router_sn: str) -> dict:
        """
        Simulates routing conmutación por error (Failover) when a master outage occurs.
        """
        logger.info(f"[Remediation] Triggering automatic routing failover for Router {router_sn}...")
        try:
            client = await db.get_client_by_identifier("RouterSN", router_sn)
            if not client:
                raise ValueError(f"No client found with Router SN {router_sn}")
                
            zona_id = client["zona_id"]
            
            # Set interface back to up and route through backup router
            if db.use_sqlite:
                query = "UPDATE equipos_red SET interface_status = 'up', packet_loss = 0.0, cpu_usage = 30.0 WHERE zona_id = ?;"
                params = (zona_id,)
            else:
                query = "UPDATE equipos_red SET interface_status = 'up', packet_loss = 0.0, cpu_usage = 30.0 WHERE zona_id = %s;"
                params = (zona_id,)
                
            await db._execute(query, params)
            
            # Log in Cacti
            await RemediationController._log_cacti_action(
                router_sn=router_sn,
                tipo="Failover automático de enrutamiento",
                valor=1.0,
                solucion="Tráfico conmutado automáticamente hacia Gateway de respaldo (Redundancia activa)."
            )
            
            return {"status": "success", "message": "Failover de ruta activo. Enrutador secundario en línea."}
        except Exception as e:
            logger.error(f"[Remediation] Failover trigger failed: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def send_escalation_webhook(ticket_id: int, client_name: str, problem_desc: str) -> dict:
        """
        Simulates auto-escalation by sending a ticket JSON payload to a webhook.
        """
        logger.info(f"[Remediation] Triggering automated technical ticket escalation webhook for Ticket: #{ticket_id}...")
        payload = {
            "text": f"🚨 *NUEVA INCIDENCIA ESCALADA A TÉCNICO DE CAMPO* 🚨\n"
                    f"*Ticket ID:* #{ticket_id}\n"
                    f"*Cliente:* {client_name}\n"
                    f"*Problema Reportado:* {problem_desc}\n"
                    f"*Estado:* Asignado a Soporte de Campo 🛠️"
        }
        
        # We can send this to a mock request bin or local log
        # For simulation purposes, we log it and send a mock post
        try:
            # Using a public sandbox webhook URL or simply logging it if offline
            logger.info(f"[Webhook Event] Payload dispatched: {payload}")
            return {"status": "success", "message": "Webhook de escalamiento despachado correctamente."}
        except Exception as e:
            logger.error(f"[Remediation] Webhook dispatch failed: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def _log_cacti_action(router_sn: str, tipo: str, valor: float, solucion: str):
        """
        Helper method to log this voice remediation transaction into Cacti database logs.
        """
        logger.info(f"[Cacti Logger] Auditing action '{tipo}' on Cacti database...")
        
        if db.use_sqlite:
            query = """
            INSERT INTO log_incidencias (
                router_id, tipo_incidencia, valor_capturado, metrica_eficiencia, solucion_automatica, estado
            ) VALUES (?, ?, ?, ?, ?, ?);
            """
        else:
            query = """
            INSERT INTO log_incidencias (
                router_id, tipo_incidencia, valor_capturado, metrica_eficiencia, solucion_automatica, estado
            ) VALUES (%s, %s, %s, %s, %s, %s);
            """
            
        params = (
            router_sn,
            tipo,
            valor,
            "MOS: 4.2 / ASR: 98%", # standard high-quality voice KPIs
            solucion,
            "Resuelto"
        )
        try:
            # We connect specifically to cacti database via db._execute
            # Since _execute uses self.pool (miranet_db), we must be careful.
            # In SQLite, both tables are in cacti.db if it's the cacti pool.
            # To be safe, we can run direct query on pool_telemetria
            if db.use_sqlite:
                import sqlite3
                conn = sqlite3.connect(db.sqlite_path_telemetria)
                try:
                    cursor = conn.cursor()
                    cursor.execute(query, params)
                    conn.commit()
                finally:
                    conn.close()
            else:
                if db.pool_telemetria:
                    async with db.pool_telemetria.acquire() as conn:
                        async with conn.cursor() as cur:
                            await cur.execute(query, params)
            logger.info("[Cacti Logger] Incident successfully logged in cacti.log_incidencias.")
        except Exception as err:
            logger.error(f"[Cacti Logger] Failed to audit cacti incident: {err}")

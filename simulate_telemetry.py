import time
import random
import threading
import json
import urllib.request
from datetime import datetime

# API Connection Settings (Exposed on public port 8000)
API_CONFIG = {
    'host': '165.227.80.77',
    'port': 8000
}

class TelemetrySimulator:
    def __init__(self):
        self.running = False
        self.simulation_thread = None
        self.mode = "NORMAL"  # Modes: NORMAL, LAG_SPIKE, OFFLINE
        self.router_id = "RT000002"
        self.packets_inserted = 0

    def log_telemetry(self, latency):
        try:
            url = f"http://{API_CONFIG['host']}:{API_CONFIG['port']}/api/v1/telemetry/report"
            payload = {"router_id": self.router_id, "latencia": latency}
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url, 
                data=data, 
                headers={'Content-Type': 'application/json'}, 
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    self.packets_inserted += 1
                    return True
            return False
        except Exception as e:
            print(f"\n[ERROR] No se pudo escribir telemetría vía API: {e}")
            return False

    def log_incident(self, tipo, valor, metrica, solucion):
        try:
            url = f"http://{API_CONFIG['host']}:{API_CONFIG['port']}/api/v1/telemetry/incident"
            payload = {
                "router_id": self.router_id,
                "tipo_incidencia": tipo,
                "valor_capturado": valor,
                "metrica_eficiencia": metrica,
                "solucion_automatica": solucion
            }
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url, 
                data=data, 
                headers={'Content-Type': 'application/json'}, 
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    print(f"\n[AUDITORÍA] Incidencia registrada vía API: {tipo} | Estado: Resuelto")
                    return True
            return False
        except Exception as e:
            print(f"\n[ERROR] No se pudo escribir incidencia vía API: {e}")
            return False

    def check_agent_resolution(self):
        """
        Check if the voice agent resolved the issue by updating the zone status to 'operativo' in miranet_db via the API.
        """
        try:
            url = f"http://{API_CONFIG['host']}:{API_CONFIG['port']}/api/v1/cliente/buscar?type=RouterSN&value={self.router_id}"
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    res_data = json.loads(response.read().decode('utf-8'))
                    client = res_data.get("client")
                    if client and client.get("zona_estado", "").lower() == 'operativo':
                        return True
        except Exception:
            pass
        return False

    def run_simulation_loop(self):
        print(f"\n[SIMULACIÓN INICIADA] Transmitiendo ráfagas SNMP de {self.router_id}...")
        while self.running:
            # Check if agent resolved the issue
            if self.mode != "NORMAL" and self.check_agent_resolution():
                print(f"\n  [SISTEMA] ¡Remediación detectada! El agente restauró el servicio para {self.router_id}. Retornando a tráfico NORMAL.")
                self.mode = "NORMAL"

            if self.mode == "NORMAL":
                latency = round(random.uniform(10.0, 32.0), 2)
                self.log_telemetry(latency)
                print(f"\r  [SNMP Live] {datetime.now().strftime('%H:%M:%S')} - Router: {self.router_id} | Latencia: {latency} ms (Estable)", end="", flush=True)
                time.sleep(2.0)
            
            elif self.mode == "LAG_SPIKE":
                # Keep generating high latency until resolved
                latency = round(random.uniform(75.0, 115.0), 2)
                self.log_telemetry(latency)
                print(f"\r  [SNMP Warning] {datetime.now().strftime('%H:%M:%S')} - Router: {self.router_id} | Latencia: {latency} ms (SPIKE CRÍTICO)", end="", flush=True)
                time.sleep(2.0)
                
            elif self.mode == "OFFLINE":
                # Keep generating offline timeouts until resolved
                latency = round(random.uniform(2500.0, 4000.0), 2)
                self.log_telemetry(latency)
                print(f"\r  [SNMP Error] {datetime.now().strftime('%H:%M:%S')} - Router: {self.router_id} | Conexión: Offline (Timeout: {latency} ms)", end="", flush=True)
                time.sleep(2.0)

    def start(self):
        if not self.running:
            self.running = True
            self.simulation_thread = threading.Thread(target=self.run_simulation_loop)
            self.simulation_thread.daemon = True
            self.simulation_thread.start()

    def stop(self):
        self.running = False
        if self.simulation_thread:
            self.simulation_thread.join(timeout=1.0)

def main_menu():
    simulator = TelemetrySimulator()
    
    # Verify API Gateway connection on startup
    try:
        url = f"http://{API_CONFIG['host']}:{API_CONFIG['port']}/health"
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                api_status = f"ONLINE (Puerto {API_CONFIG['port']})"
            else:
                api_status = f"HTTP ERROR {response.status}"
    except Exception as e:
        api_status = f"DESCONECTADO ({e})"
        print(f"[ALERTA] El Servidor del Agente de Voz no está respondiendo en el puerto {API_CONFIG['port']}.")
        print(f"Detalles: {e}")
        return

    simulator.start()

    while True:
        print("\n" + "="*60)
        print("     ORQUESTRADOR DE SIMULACIÓN DE TELEMETRÍA - MIRANET SAC")
        print("="*60)
        print(f" Servidor API: HTTP {api_status}")
        print(f" Paquetes SNMP enviados en esta sesión: {simulator.packets_inserted}")
        print(f" Modo de simulación activo: {simulator.mode} | Router SN: {simulator.router_id}")
        print("-"*60)
        print("  [1] Tráfico NORMAL (Latencia 10-32ms, canal de voz estable)")
        print("  [2] Provocar FALLA LÓGICA (Pico de latencia >60ms, caída de MOS)")
        print("  [3] Provocar CAÍDA FÍSICA (Pérdida/Desconexión de paquetes, timeout)")
        print("  [4] Cambiar Router a Simular (ej: RT000001, RT000002)")
        print("  [5] Detener y Salir de la simulación")
        print("="*60)
        
        opcion = input("Selecciona una opción (1-5): ").strip()
        
        if opcion == "1":
            simulator.mode = "NORMAL"
            print("\n>> Cambiando a Modo NORMAL. Observa la consola de Cacti...")
            time.sleep(1.0)
        elif opcion == "2":
            simulator.mode = "LAG_SPIKE"
            print(f"\n>> Inyectando FALLA LÓGICA para {simulator.router_id}. Habla con el Agente...")
            time.sleep(1.0)
        elif opcion == "3":
            simulator.mode = "OFFLINE"
            print(f"\n>> Inyectando CAÍDA DE CONEXIÓN para {simulator.router_id}. Habla con el Agente...")
            time.sleep(1.0)
        elif opcion == "4":
            nuevo_sn = input(f"Ingrese Serial Number del Router (Actual: {simulator.router_id}): ").strip().upper()
            if nuevo_sn:
                simulator.router_id = nuevo_sn
                print(f"\n>> Ahora simulando telemetría para: {simulator.router_id}")
            time.sleep(1.0)
        elif opcion == "5":
            print("\nDeteniendo simulador de telemetría...")
            simulator.stop()
            break
        else:
            print("\n[Opción Inválida] Por favor selecciona de 1 a 5.")
            time.sleep(1.0)

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nSimulación interrumpida por el usuario. Saliendo...")

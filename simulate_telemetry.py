import time
import random
import threading
import mysql.connector
from datetime import datetime

# Database Connection Settings
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3307,
    'user': 'root',
    'password': '',
    'database': 'cacti'
}

class TelemetrySimulator:
    def __init__(self):
        self.running = False
        self.simulation_thread = None
        self.mode = "NORMAL"  # Modes: NORMAL, LAG_SPIKE, OFFLINE
        self.router_id = "RT000002"
        self.packets_inserted = 0

    def connect_db(self):
        return mysql.connector.connect(**DB_CONFIG)

    def log_telemetry(self, latency):
        try:
            conn = self.connect_db()
            cursor = conn.cursor()
            query = "INSERT INTO telemetria_snmp (router_id, latencia) VALUES (%s, %s);"
            cursor.execute(query, (self.router_id, latency))
            conn.commit()
            cursor.close()
            conn.close()
            self.packets_inserted += 1
            return True
        except Exception as e:
            print(f"\n[ERROR] No se pudo escribir en MySQL cacti: {e}")
            return False

    def log_incident(self, tipo, valor, metrica, solucion):
        try:
            conn = self.connect_db()
            cursor = conn.cursor()
            query = """
            INSERT INTO log_incidencias (router_id, tipo_incidencia, valor_capturado, metrica_eficiencia, solucion_automatica, estado)
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            cursor.execute(query, (self.router_id, tipo, valor, metrica, solucion, "Resuelto"))
            conn.commit()
            cursor.close()
            conn.close()
            print(f"\n[AUDITORÍA] Incidencia registrada en log_incidencias: {tipo} | Estado: Resuelto")
            return True
        except Exception as e:
            print(f"\n[ERROR] No se pudo escribir incidencia: {e}")
            return False

    def check_agent_resolution(self):
        """
        Check if the voice agent resolved the issue by updating the zone status to 'operativo' in miranet_db.
        """
        try:
            conn = mysql.connector.connect(
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database='miranet_db'
            )
            cursor = conn.cursor(dictionary=True)
            query = """
                SELECT z.estado 
                FROM clientes c 
                JOIN zonas z ON c.zona_id = z.id 
                WHERE c.router_sn = %s;
            """
            cursor.execute(query, (self.router_id,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if row and row['estado'].lower() == 'operativo':
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
    
    # Verify DB connection on startup
    try:
        conn = simulator.connect_db()
        conn.close()
        db_status = "ONLINE (Puerto 3307)"
    except Exception as e:
        db_status = f"DESCONECTADO ({e})"
        print(f"[ALERTA] MySQL no está respondiendo en el puerto 3307. Asegúrate de encender XAMPP.")
        print(f"Detalles: {e}")
        return

    simulator.start()

    while True:
        print("\n" + "="*60)
        print("     ORQUESTRADOR DE SIMULACIÓN DE TELEMETRÍA - MIRANET SAC")
        print("="*60)
        print(f" Base de Datos: MySQL 'cacti' | Estado: {db_status}")
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

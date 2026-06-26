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

    def run_simulation_loop(self):
        print(f"\n[SIMULACIÓN INICIADA] Transmitiendo ráfagas SNMP de {self.router_id}...")
        while self.running:
            if self.mode == "NORMAL":
                latency = round(random.uniform(10.0, 32.0), 2)
                self.log_telemetry(latency)
                print(f"\r  [SNMP Live] {datetime.now().strftime('%H:%M:%S')} - Router: {self.router_id} | Latencia: {latency} ms (Estable)", end="", flush=True)
                time.sleep(2.0)
            
            elif self.mode == "LAG_SPIKE":
                # Generate 5 packets of high latency
                print("\n  [INTRUSIÓN] Inyectando ráfaga de Latencia Crítica...")
                # Log incident to DB
                self.log_incident(
                    tipo="Pico de Latencia Crítica",
                    valor=85.4,
                    metrica="MOS bajó a 2.5 (Poor Quality)",
                    solucion="Aprovisionamiento automático de QoS y reajuste lógico de canal"
                )
                for _ in range(5):
                    if not self.running:
                        break
                    latency = round(random.uniform(75.0, 115.0), 2)
                    self.log_telemetry(latency)
                    print(f"\r  [SNMP Warning] {datetime.now().strftime('%H:%M:%S')} - Latencia: {latency} ms (SPIKE CRÍTICO)", end="", flush=True)
                    time.sleep(2.0)
                
                # Back to normal automatically
                print("\n  [SIMULACIÓN] Remediada automáticamente. Retornando a tráfico NORMAL.")
                self.mode = "NORMAL"

            elif self.mode == "OFFLINE":
                print("\n  [INTRUSIÓN] Simulando desconexión física local del canal de voz...")
                self.log_incident(
                    tipo="Caída de Conexión Local",
                    valor=3500.0,
                    metrica="ASR bajó a 82.0% (Degradación Crítica)",
                    solucion="Reconexión en caliente y restauración de contexto de diálogo en buffer"
                )
                for _ in range(5):
                    if not self.running:
                        break
                    latency = round(random.uniform(2500.0, 4000.0), 2)
                    self.log_telemetry(latency)
                    print(f"\r  [SNMP Error] {datetime.now().strftime('%H:%M:%S')} - Conexión: Offline (Timeout: {latency} ms)", end="", flush=True)
                    time.sleep(2.0)

                print("\n  [SIMULACIÓN] Reconexión exitosa. Retornando a tráfico NORMAL.")
                self.mode = "NORMAL"

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
        print(f" Modo de simulación activo: {simulator.mode}")
        print("-"*60)
        print("  [1] Tráfico NORMAL (Latencia 10-32ms, canal de voz estable)")
        print("  [2] Provocar FALLA LÓGICA (Pico de latencia >60ms, caída de MOS)")
        print("  [3] Provocar CAÍDA FÍSICA (Pérdida/Desconexión de paquetes, timeout)")
        print("  [4] Detener y Salir de la simulación")
        print("="*60)
        
        opcion = input("Selecciona una opción (1-4): ").strip()
        
        if opcion == "1":
            simulator.mode = "NORMAL"
            print("\n>> Cambiando a Modo NORMAL. Observa la consola de Cacti...")
            time.sleep(1.0)
        elif opcion == "2":
            simulator.mode = "LAG_SPIKE"
            print("\n>> Inyectando FALLA LÓGICA en la telemetría SNMP. Habla con el Agente...")
            time.sleep(1.0)
        elif opcion == "3":
            simulator.mode = "OFFLINE"
            print("\n>> Inyectando CAÍDA DE CONEXIÓN. Habla con el Agente...")
            time.sleep(1.0)
        elif opcion == "4":
            print("\nDeteniendo simulador de telemetría...")
            simulator.stop()
            break
        else:
            print("\n[Opción Inválida] Por favor selecciona de 1 a 4.")
            time.sleep(1.0)

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nSimulación interrumpida por el usuario. Saliendo...")

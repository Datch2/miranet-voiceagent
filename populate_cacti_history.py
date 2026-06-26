import random
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta

def populate_cacti_data():
    connection = None
    try:
        # Connect to Cacti database on port 3307 (XAMPP isolated port)
        print("Connecting to MySQL database 'cacti' on port 3307...")
        connection = mysql.connector.connect(
            host='localhost',
            port=3307,
            user='root',
            password='',
            database='cacti'
        )

        if connection.is_connected():
            cursor = connection.cursor()
            
            # 1. Recreate table log_incidencias with updated audited telecom metrics schema
            print("Checking/recreating 'log_incidencias' table to support telecom auditing...")
            cursor.execute("DROP TABLE IF EXISTS `log_incidencias`;")
            
            create_table_query = """
            CREATE TABLE `log_incidencias` (
              `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
              `router_id` varchar(50) NOT NULL,
              `tipo_incidencia` varchar(100) NOT NULL,
              `valor_capturado` double NOT NULL,
              `metrica_eficiencia` varchar(100) NOT NULL,
              `solucion_automatica` varchar(255) NOT NULL,
              `estado` varchar(20) NOT NULL,
              `fecha_alerta` timestamp DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            cursor.execute(create_table_query)
            print("'log_incidencias' table successfully recreated.")

            # 2. Populate 150 historical records into telemetria_snmp
            print("\nGenerating 150 historical telemetry records in 'telemetria_snmp'...")
            cursor.execute("TRUNCATE TABLE telemetria_snmp;")
            
            base_time = datetime.now() - timedelta(minutes=150 * 10)
            telemetry_count = 0
            
            for i in range(150):
                record_time = base_time + timedelta(minutes=i * 10)
                
                # Normal network latency simulation
                if random.random() < 0.8:
                    latency = round(random.uniform(10.0, 35.0), 2)
                else:
                    latency = round(random.uniform(36.0, 55.0), 2)

                telemetry_insert_query = """
                INSERT INTO telemetria_snmp (router_id, latencia, recorded_at)
                VALUES (%s, %s, %s);
                """
                cursor.execute(telemetry_insert_query, ("RT000002", latency, record_time))
                telemetry_count += 1

            # 3. Insert 13 high-fidelity historical voice-efficiency incidents
            print("Generating 13 historical telecom incidents in 'log_incidencias'...")
            
            incidents_data = [
                {
                    "tipo_incidencia": "Pico de Latencia Crítica",
                    "valor_capturado": 85.0,
                    "metrica_eficiencia": "MOS bajó a 2.5 (Poor Quality)",
                    "solucion_automatica": "Failover automático a servidor secundario y ajuste dinámico de buffer"
                },
                {
                    "tipo_incidencia": "Caída de Servidor de Inferencia",
                    "valor_capturado": 120.0,
                    "metrica_eficiencia": "ASR bajó a 0.0% (No Response)",
                    "solucion_automatica": "Redirección de tráfico por ruta B hacia nodo de respaldo en la nube"
                },
                {
                    "tipo_incidencia": "Degradación de Calidad MOS",
                    "valor_capturado": 1.9,
                    "metrica_eficiencia": "MOS bajó a 1.9 (Very Poor Quality)",
                    "solucion_automatica": "Redirección inmediata de tráfico RTP por nodo de red alternativo B"
                },
                {
                    "tipo_incidencia": "Pico de Latencia Crítica",
                    "valor_capturado": 74.0,
                    "metrica_eficiencia": "ASR bajó a 82.0% (Word Recognition Error)",
                    "solucion_automatica": "Activación de redundancia FEC (Forward Error Correction) en canal de WebSocket"
                },
                {
                    "tipo_incidencia": "Caída de Conexión Local",
                    "valor_capturado": 3500.0,
                    "metrica_eficiencia": "MOS bajó a 1.0 (Session Dead)",
                    "solucion_automatica": "Reconexión en caliente y restauración de contexto de diálogo en buffer local"
                },
                {
                    "tipo_incidencia": "Pico de Latencia Crítica",
                    "valor_capturado": 68.4,
                    "metrica_eficiencia": "MOS bajó a 3.2 (Fair Quality)",
                    "solucion_automatica": "Ajuste dinámico de hilos de procesamiento en decodificador local"
                },
                {
                    "tipo_incidencia": "Degradación de Calidad MOS",
                    "valor_capturado": 2.5,
                    "metrica_eficiencia": "MOS bajó a 2.5 (Poor Quality)",
                    "solucion_automatica": "Ajuste adaptativo de jitter buffer y reducción de bitrate de Opus codec"
                },
                {
                    "tipo_incidencia": "Error de Procesamiento de Audio",
                    "valor_capturado": 100.0,
                    "metrica_eficiencia": "ASR bajó a 82.0% (High Processing Delay)",
                    "solucion_automatica": "Migración automática de hilos Whisper locales a API REST del servidor de respaldo"
                },
                {
                    "tipo_incidencia": "Error de Sincronización RTP/RTCP",
                    "valor_capturado": 120.0,
                    "metrica_eficiencia": "MOS bajó a 2.4 (Poor Synchronization)",
                    "solucion_automatica": "Resincronización de reloj y timestamps NTP en el servidor de streaming"
                },
                {
                    "tipo_incidencia": "Degradación de Calidad MOS",
                    "valor_capturado": 2.1,
                    "metrica_eficiencia": "MOS bajó a 2.1 (Poor Quality)",
                    "solucion_automatica": "Reducción adaptativa de bitrate a 16kbps en codificador de audio local"
                },
                {
                    "tipo_incidencia": "Pico de Latencia Crítica",
                    "valor_capturado": 92.1,
                    "metrica_eficiencia": "MOS bajó a 2.6 (Poor Quality)",
                    "solucion_automatica": "Limpieza en caliente y liberación de buffers de memoria RAM del proceso FastAPI"
                },
                {
                    "tipo_incidencia": "Caída de Servidor de Inferencia",
                    "valor_capturado": 500.0,
                    "metrica_eficiencia": "ASR bajó a 98.0% (Synthesizer Lag)",
                    "solucion_automatica": "Failover local a motor TTS integrado en navegador del cliente"
                },
                {
                    "tipo_incidencia": "Caída de Conexión Local",
                    "valor_capturado": 80.0,
                    "metrica_eficiencia": "ASR bajó a 82.0% (Degradación Crítica)",
                    "solucion_automatica": "Activación del limitador de tasa de muestreo y descarte de tramas silenciosas"
                }
            ]


            incident_count = 0
            for idx, inc in enumerate(incidents_data):
                # Distribute incident times in the past (e.g. spread over 24 hours)
                incident_time = base_time + timedelta(hours=idx * 2)
                
                incident_insert_query = """
                INSERT INTO log_incidencias (router_id, tipo_incidencia, valor_capturado, metrica_eficiencia, solucion_automatica, estado, fecha_alerta)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """
                cursor.execute(incident_insert_query, (
                    "RT000002",
                    inc["tipo_incidencia"],
                    inc["valor_capturado"],
                    inc["metrica_eficiencia"],
                    inc["solucion_automatica"],
                    "Resuelto",  # Always ends in "Resuelto" for self-recovery mapping
                    incident_time
                ))
                incident_count += 1

            connection.commit()
            print(f"\n--- SUCCESS ---")
            print(f"Total telemetry records inserted into 'telemetria_snmp': {telemetry_count}")
            print(f"Total audited incidents inserted into 'log_incidencias': {incident_count}")

    except Error as e:
        print(f"Error during database operation: {e}")
        if connection:
            connection.rollback()
            print("Transaction rolled back.")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("\nMySQL connection closed.")

if __name__ == "__main__":
    populate_cacti_data()

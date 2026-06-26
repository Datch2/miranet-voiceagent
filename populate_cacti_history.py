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
            
            # 1. Create table log_incidencias if it does not exist
            print("Checking/creating 'log_incidencias' table...")
            create_table_query = """
            CREATE TABLE IF NOT EXISTS `log_incidencias` (
              `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
              `router_id` varchar(50) NOT NULL,
              `tipo_incidencia` varchar(100) NOT NULL,
              `valor_capturado` double NOT NULL,
              `estado` varchar(20) NOT NULL,
              `fecha_alerta` timestamp DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            cursor.execute(create_table_query)
            print("'log_incidencias' table is ready.")

            # 2. Populate 150 historical records in a loop
            print("\nGenerating 150 historical telemetry records and checking for incident alerts...")
            telemetry_count = 0
            incident_count = 0
            
            # Start timestamps in the past and move forward
            base_time = datetime.now() - timedelta(minutes=150 * 10)
            
            for i in range(150):
                # Generate chronological datetime
                record_time = base_time + timedelta(minutes=i * 10)
                
                # Simulating router latencies (mix of normal and high latency pikes)
                # 70% chance of normal latency (10-35ms)
                # 30% chance of critical latency spikes (36-95ms)
                if random.random() < 0.7:
                    latency = round(random.uniform(10.0, 35.0), 2)
                else:
                    latency = round(random.uniform(36.0, 95.0), 2)

                # Insert telemetry record into telemetria_snmp
                telemetry_insert_query = """
                INSERT INTO telemetria_snmp (router_id, latencia, recorded_at)
                VALUES (%s, %s, %s);
                """
                cursor.execute(telemetry_insert_query, ("RT000002", latency, record_time))
                telemetry_count += 1

                # Requerimiento Técnico de Alerta: latency > 50.0 ms
                if latency > 50.0:
                    estado = random.choice(["Activo", "Resuelto"])
                    incident_insert_query = """
                    INSERT INTO log_incidencias (router_id, tipo_incidencia, valor_capturado, estado, fecha_alerta)
                    VALUES (%s, %s, %s, %s, %s);
                    """
                    cursor.execute(incident_insert_query, (
                        "RT000002",
                        "Latencia Crítica en Agente de Voz",
                        latency,
                        estado,
                        record_time
                    ))
                    incident_count += 1

            connection.commit()
            print(f"\n--- SUCCESS ---")
            print(f"Total telemetry records inserted into 'telemetria_snmp': {telemetry_count}")
            print(f"Total alert records mirrored into 'log_incidencias' (> 50.0 ms): {incident_count}")

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

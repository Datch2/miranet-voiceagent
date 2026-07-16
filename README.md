# Miranet VoiceAgent — Sistema de Voz Interactivo y Monitoreo de Red

**Miranet VoiceAgent** es una plataforma avanzada de soporte de voz e inteligencia artificial en tiempo real para la empresa de telecomunicaciones **Miranet SAC**. 

El sistema combina un **Asistente de Voz y Chat por IA** (que diagnostica averías conversando con el cliente) y una **Arquitectura de Monitoreo Cacti/SNMP** que recolecta telemetría en tiempo real de múltiples routers de abonados, simulando escenarios reales de caídas físicas y saturación de CPU.

---

## 🏗️ Arquitectura del Sistema

El proyecto maneja una arquitectura distribuida de tipo **Mánager - Agente** desplegada mediante contenedores Docker en múltiples servidores en la nube (DigitalOcean):

```
                       ┌──────────────────────────────────────────────┐
                       │      SERVIDOR CENTRAL (165.227.XX.XX)        │
                       │                                              │
                       │    ┌────────────────┐   ┌────────────────┐   │
                       │    │  Web Frontend  │   │  FastAPI (Py)  │   │
                       │    │  (Chat/Voz UI) │◄─►│   Backend      │   │
                       │    └────────────────┘   └──────┬─────────┘   │
                       │                                │ (Lee logs)  │
                       │    ┌────────────────┐          ▼             │
                       │    │  Cacti Web UI  │     [network.log]      │
                       │    │ (php:8.1-apache│          ▲             │
                       │    └───────┬────────┘          │ (Escribe)   │
                       │            │ (Poller)          │             │
                       │            ▼                   │             │
                       │    ┌────────────────┐   ┌──────┴─────────┐   │
                       │    │   MySQL 8.0    │   │  Fibonacci.py  │   │
                       │    │  (cacti_db)    │   │   (Monitor)    │   │
                       │    └────────────────┘   └──────┬─────────┘   │
                       └────────────────────────────────┼─────────────┘
                                                        │
                              ┌─────────────────────────┴─────────────────────────┐
                              ▼ (SNMP Port 161 UDP)                               ▼ (SNMP Port 161 UDP)
              ┌───────────────────────────────┐                   ┌───────────────────────────────┐
              │  CLIENTE NODE 1 (RT000002)    │                   │  CLIENTE NODE 2 (RT000001)    │
              │       IP: 146.190.XX.XX       │                   │       IP: 147.182.XX.XX       │
              │  [Contenedor Docker snmp_client]│                 │  [Contenedor Docker snmp_client]│
              └───────────────────────────────┘                   └───────────────────────────────┘
```

### 1. Servidor Central (Mánager)
IP Pública: `165.227.XX.XX`. Aloja y orquesta los servicios centrales:
*   **Web Portal (Frontend):** Interfaz web interactiva cliente-operador con osciloscopio de audio.
*   **Voice Agent API (Backend):** Lógica del agente en Python (`responder.py`). Analiza el DNI del cliente, lee el log `/root/miranet-voiceagent/logs/network.log` para revisar el router asociado y genera la respuesta técnica usando el LLM.
*   **Motor LLM (Ollama):** Servicio local de IA (modelo LLaMA) para procesar el lenguaje natural.
*   **Cacti Container:** Servidor Apache + PHP 8.1 oficial (`php:8.1-apache`) con las herramientas del sistema Linux (`rrdtool` y `snmp` client utilities) y el módulo gráfico de PHP (`gd`) compilados en caliente al encender el contenedor.
*   **Database Container (MySQL 8.0):** Almacena las tablas históricas y el esquema de Cacti v1.2.31. Expuesto localmente en el puerto `3308` para desarrollo y `3306` internamente.
*   **Monitor Fibonacci (`fibonacci.py`):** Script independiente que consulta cada 2 segundos a los clientes y escribe en `network.log`. Aplica la serie matemática de Fibonacci para desfasar los re-intentos de ping en caso de pérdidas de conexión.

### 2. Nodos Clientes (Agentes)
Representan los enrutadores de los abonados en droplets independientes de Linux:
*   **Cliente 1 (RT000002) - IP `146.190.XX.XX`:** En línea. Corre un contenedor `snmp_client` exponiendo métricas del sistema.
*   **Cliente 2 (RT000001) - IP `147.182.XX.XX`:** Utilizado para simular fallas apagando su agente.
*   *Nota: Por motivos de seguridad, los clientes tienen configurado su firewall para responder a las consultas SNMP (Puerto 161 UDP) únicamente si provienen de la IP del Servidor Central.*

---

## 📂 Estructura del Proyecto

```text
/root/miranet-voiceagent/
├── backend/                        # Lógica del Agente de Voz y WebSockets
│   ├── agents/
│   │   ├── responder.py            # Analizador LLM y lector de logs SNMP
│   │   └── orchestrator.py         # Orquestador principal del flujo
│   └── main.py                     # Inicializador del backend FastAPI
│
├── cacti/                          # Archivos de la consola web de Cacti 1.2.26+
│   ├── include/config.php          # Configuración de base de datos
│   └── ...
│
├── frontend/                       # Archivos de la interfaz web del cliente
│   ├── agent.html                  # Chat interactivo y grabador de voz
│   ├── index.css                   # Estilo moderno Glassmorphism
│   └── index.js                    # WebSockets de audio y lógica cliente
│
├── scratch/                        # Carpeta de herramientas y scripts
│   └── fibonacci.py                # Script monitor SNMP de clientes
│
├── cacti_full.sql                  # Volcado de BD oficial de Cacti con telemetría
├── docker-compose.yml              # Entorno de desarrollo local
├── docker-compose.prod.yml         # Entorno de producción (Nube)
├── requirements.txt                # Dependencias de Python
└── README.md                       # Documentación del sistema (Este archivo)
```

---

## 🏁 Instrucciones de Despliegue y Ejecución

### 1. Iniciar los Contenedores en el Servidor Central
Asegúrate de que no haya otros servicios web en uso y corre los comandos en la carpeta del Servidor Central:

```bash
# Apagar contenedores huérfanos y levantar el proyecto de forma limpia
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d --force-recreate
```
*(Espera 45 segundos la primera vez para permitir que el contenedor de Apache descargue y compile las librerías gráficas de RRDtool/GD en segundo plano).*

### 2. Configurar Permisos de Archivos y Base de Datos
Ejecuta estos tres comandos obligatorios para asegurar que Cacti pueda graficar:

```bash
# A. Dar propiedad de las carpetas a Apache (www-data)
docker exec miranet-cacti-web chown -R www-data:www-data /var/www/html/cacti/rra /var/www/html/cacti/log

# B. Registrar la versión moderna de RRDtool en la BD de Cacti
docker exec -i miranet-mysql-db mysql -uroot -pMiranetSecureDb2026! cacti -e "
  UPDATE settings SET value = '1.7.x' WHERE name = 'rrdtool_version';
"

# C. Registrar las rutas correctas de los ejecutables de Linux en la BD
docker exec -i miranet-mysql-db mysql -uroot -pMiranetSecureDb2026! cacti -e "
  INSERT INTO settings (name, value) VALUES 
    ('path_rrdtool', '/usr/bin/rrdtool'),
    ('path_php_binary', '/usr/local/bin/php'),
    ('path_snmpget', '/usr/bin/snmpget'),
    ('path_snmpwalk', '/usr/bin/snmpwalk'),
    ('path_snmpbulkwalk', '/usr/bin/snmpbulkwalk'),
    ('path_snmpgetnext', '/usr/bin/snmpgetnext'),
    ('path_snmpset', '/usr/bin/snmpset'),
    ('path_snmptrap', '/usr/bin/snmptrap')
  ON DUPLICATE KEY UPDATE value = VALUES(value);
"
```

### 3. Levantar los Monitores e Importadores
Desde el Servidor Central:

```bash
# A. Automatizar el poller de Cacti cada minuto en el sistema host
(crontab -l 2>/dev/null; echo "* * * * * docker exec -u www-data miranet-cacti-web php /var/www/html/cacti/poller.php >/dev/null 2>&1") | crontab -

# B. Importar plantillas de Cacti por CLI
docker exec miranet-cacti-web php /var/www/html/cacti/cli/import_package.php --filename=/var/www/html/cacti/install/templates/Generic_SNMP_Device.xml.gz

# C. Levantar el Monitor de logs Fibonacci en background
nohup python3 /root/miranet-voiceagent/scratch/fibonacci.py > /dev/null 2>&1 &
```

---

## 🎮 Simulación de Escenarios para la Defensa

### Escenario A: Caída Total Física de Red (Cliente 2 - DNI `12345678`)
1.  **Provocar la falla:** Entra en el SSH del **Cliente 2 (`147.182.XX.XX`)** y apaga su agente:
    ```bash
    docker stop snmp_client
    ```
2.  El Monitor Fibonacci registrará el Timeout en `network.log` aplicando la re-intento exponencial.
3.  **Probar el Agente:** Entra al portal del chat, ingresa el DNI `12345678` y di *"No tengo internet"*. El Agente de Voz leerá el log de timeout y diagnosticará una avería física.
4.  **Recuperar el router:** Corre `docker start snmp_client` en el Cliente 2 para ponerlo en línea nuevamente.

### Escenario B: Saturación por Consumo de CPU (Cliente 1 - DNI `87654321`)
1.  **Provocar la saturación:** Entra en el SSH del **Cliente 1 (`146.190.XX.XX`)** y corre:
    ```bash
    cat /dev/urandom | gzip -9 > /dev/null &
    ```
2.  La CPU del Cliente subirá al 100%. Fibonacci y Cacti registrarán `CPU: 100.0%` en tiempo real.
3.  **Probar el Agente:** Entra al portal del chat, ingresa el DNI `87654321` y di *"Mi internet está lento"*. El agente leerá la sobrecarga y te recomendará reiniciar el router o detener descargas masivas.
4.  **Liberar el router:** Corre `killall gzip` en el Cliente 1.

### Escenario C: Ciclo Autónomo de Caídas y Estrés (24 horas)
Puedes dejar corriendo tareas automáticas en los clientes para que se enciendan/apaguen solos cíclicamente:
*   **En el Cliente 1 (Estrés cíclico cada 10 mins):**
    ```bash
    (crontab -l 2>/dev/null; echo "*/10 * * * * timeout 120 bash -c 'cat /dev/urandom | gzip -9 > /dev/null'") | crontab -
    ```
*   **En el Cliente 2 (Caída física cíclica cada 30 mins):**
    ```bash
    (crontab -l 2>/dev/null; echo "15,45 * * * * docker stop snmp_client && sleep 300 && docker start snmp_client") | crontab -
    ```

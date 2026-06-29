# Miranet VoiceAgent — Sistema de Voz Interactivo y Remediación de Red (2026)

**Miranet VoiceAgent** es una plataforma avanzada de soporte de voz e inteligencia artificial en tiempo real para la empresa de telecomunicaciones **Miranet SAC**. 

El sistema actúa simultáneamente como **Operadora Automática** (conversando con el cliente por voz o texto) y **Orquestador de Infraestructura** (diagnosticando la red, disparando scripts de autorecuperación en caliente y reportando la telemetría en vivo a un panel de control).

---

## 🚀 Características Principales

1. **Procesamiento de Voz Asíncrono de Baja Latencia:** Captura de micrófono en mono PCM de 16-bit a 16kHz y transmisión continua por WebSockets.
2. **Transcripción Local Rápida:** Reconocimiento de voz local con **OpenAI Whisper (modelo `tiny`)** en CPU/GPU para eliminar dependencias externas en la nube.
3. **Núcleo de Inteligencia Artificial (Phi-3 Mini 3.8B):** Integrado mediante **Ollama local** (reemplazando a Mistral para reducir el consumo de RAM a ~2.2 GB y procesar la respuesta en **menos de 2 segundos**):
   - **Clasificación del Incidente:** Gravedad de la falla (`bajo`, `medio`, `alto`, `critico`).
   - **Diagnóstico y Causa Raíz:** Cruce de la descripción hablada del cliente con las métricas del router obtenidas en vivo.
   - **Salida en JSON Estricto:** Procesamiento seguro de datos estructurados para automatizar las reparaciones.
4. **Motor de Remediación Activa (Autorecuperación):**
   - *Aprovisionamiento de QoS:* Restablece y optimiza la velocidad en routers saturados (baja CPU y pérdida al 0%).
   - *Interface Flapping:* Simula el reinicio físico apagando y encendiendo la WAN en la base de datos si la interfaz cae.
   - *Failover de Rutas:* Desvía el tráfico hacia gateways de respaldo ante averías masivas en la zona.
   - *Vaciado de Caché:* Limpia registros DNS locales del servidor (`ipconfig /flushdns`).
   - *Escalamiento Técnico:* Despacha un webhook JSON de alerta a soporte técnico para roturas físicas de cable.
5. **Consola Cacti Dinámica (`http://localhost/cacti/`):** 
   - Gráfico de latencia en tiempo real (últimos 20 ticks) mediante **Chart.js**.
   - Mapeo dinámico de **24 routers de clientes** desde MySQL con estado en vivo (`Activo` / `Offline`).
   - Historial de incidencias resueltas (`log_incidencias`) con auditoría de métricas de eficiencia.
6. **Simulador de Telemetría Cerrado (`simulate_telemetry.py`):**
   - Inyecta anomalías de red (lag crítico o caídas) en la base de datos para pruebas.
   - **Bucle Cerrado:** El simulador monitoriza la base de datos y se apaga de forma autónoma en cuanto capta que el agente de voz solucionó el problema del router del cliente.
   - Permite seleccionar cuál de los routers de los clientes (`RT000001` a `RT000024`) simular desde un menú interactivo.
7. **Persistencia Dual (MySQL & SQLite):** Operación en **MySQL (puerto 3307)** con cambio automático a **SQLite local** si el servidor principal está apagado.

---

## 🛠️ Tecnologías y Herramientas

* **Lenguaje:** [Python 3.10+](https://www.python.org/) para backend y automatización.
* **APIs & WebSockets:** [FastAPI](https://fastapi.tiangolo.com/) y [Uvicorn](https://www.uvicorn.org/) para flujo binario síncrono.
* **IA Local:** OpenAI Whisper (STT) + Ollama Phi-3 (LLM) + Web Speech API (TTS en navegador).
* **Base de Datos:** MySQL (XAMPP - puerto 3307) para negocio (`miranet_db`) y telemetría (`cacti`).
* **Frontend:** HTML5 + Vanilla CSS moderno (Glassmorphism, variables HSL) + Canvas 2D osciloscopio de voz.

---

## 📂 Estructura del Proyecto

El código está estructurado en el **Disco D** de la siguiente manera:

```text
D:/miranet-voiceagent/
│
├── backend/                        # Servidor de FastAPI y Orquestación
│   ├── agents/                     # Agentes autónomos
│   │   ├── transcriber.py          # Transcriptor Whisper local
│   │   ├── responder.py            # Analizador LLM y clasificador
│   │   ├── network_monitor.py      # Calculador de jitter y pérdida de paquetes
│   │   └── orchestrator.py         # Orquestador del flujo y base de datos
│   │
│   ├── db/                         # Configuración y sentencias de base de datos
│   │   └── database.py             # Semillero y conector MySQL/SQLite
│   │
│   ├── utils/                      # Módulos de soporte técnico
│   │   └── remediation.py          # Controlador de remediación y pings
│   │
│   ├── config.py                   # Lector de variables del entorno (.env)
│   └── main.py                     # Inicializador del servidor ASGI
│
├── frontend/                       # Código de la aplicación web cliente
│   ├── agent.html                  # Panel de interacción y voz
│   ├── index.css                   # Diseño visual translúcido glassmorphism
│   └── index.js                    # Grabadora de micrófono y WebSockets
│
├── models/                         # Caché local de Whisper
├── scratch/                        # Scripts de verificación y semillado
├── simulate_telemetry.py           # Simulador interactivo de fallas de red
└── README.md                       # Documentación principal
```

*Nota: La interfaz web de telemetría se aloja en el directorio Apache de XAMPP: `D:\XAMMP\htdocs\cacti\index.php`.*

---

## ⚙️ Configuración e Instalación

### Requisitos Previos
1. Tener instalado [Python 3.10+](https://www.python.org/downloads/).
2. Tener instalado y corriendo [Ollama](https://ollama.com/).
3. Iniciar el panel de control de XAMPP (Apache en puerto 80 y MySQL en puerto 3307).

### Paso 1: Instalar Dependencias de Python
Abre una terminal y ejecuta:
```bash
pip install -r requirements.txt
```

### Paso 2: Descargar Phi-3 en Ollama
Con Ollama corriendo en segundo plano:
```bash
ollama pull phi3
```

### Paso 3: Configurar Variables de Entorno
Crea o edita tu archivo `.env` en la raíz del proyecto:
```ini
# MySQL Database Config
DB_HOST=127.0.0.1
DB_PORT=3307
DB_USER=root
DB_PASSWORD=
DB_NAME=miranet_db
DB_NAME_TELEMETRIA=cacti

# Ollama Settings
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=phi3

# Whisper Settings
WHISPER_MODEL_NAME=tiny
WHISPER_DOWNLOAD_ROOT=D:\miranet-voiceagent\models\whisper
```

---

## 🏁 Ejecución del Sistema

### 1. Arrancar el Backend (FastAPI)
```bash
python backend/main.py
```

### 2. Arrancar el Simulador de Telemetría
En otra terminal independiente:
```bash
python simulate_telemetry.py
```
*Tip: Selecciona la opción `[4]` para cambiar el router a `RT000001` (Diego Torres) y luego la opción `[2]` para inyectar una falla de red.*

### 3. Abrir en el Navegador
*   **Panel del Cliente:** Ingresa a [http://localhost:8000/](http://localhost:8000/) y loguéate con el DNI de Diego Torres (`12345678`).
*   **Consola Cacti:** Ingresa a [http://localhost/cacti/](http://localhost/cacti/) para ver las latencias del router y su estado en tiempo real.
*   **Conversar/Arreglar:** Pídele al bot *"Mi internet está lento"*. Observa cómo el orquestador aplica el script, Cacti se normaliza solo y la pantalla de Diego Torres pasa a estar en **`OPERATIVO`**.

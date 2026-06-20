import sqlite3
import asyncio
import logging
from pathlib import Path
import aiomysql
from backend.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Database")

class DatabaseManager:
    def __init__(self):
        self.pool: aiomysql.Pool | None = None
        self.use_sqlite = False
        self.use_supabase = False
        self.supabase_client = None
        self.sqlite_path = Path(__file__).resolve().parent / "voiceagent.db"

    async def ensure_mysql_db_exists(self):
        """Connect to MySQL and create the database if it doesn't exist."""
        conn = await aiomysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            autocommit=True
        )
        try:
            async with conn.cursor() as cur:
                # Sanitized DB name creation
                db_name = settings.DB_NAME.replace("`", "")
                await cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`;")
            logger.info(f"MySQL database `{db_name}` checked/created.")
        finally:
            conn.close()

    async def connect(self):
        """Initialize Supabase client, connection pool, or fallback to SQLite."""
        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            try:
                logger.info("Initializing Supabase Client (Official SDK)...")
                from supabase import create_client
                self.supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                self.use_supabase = True
                logger.info("Supabase Client initialized successfully.")
                return
            except Exception as se_err:
                logger.error(f"Failed to initialize Supabase Client: {se_err}. Falling back to local databases...")

        try:
            logger.info(f"Attempting to connect to MySQL at {settings.DB_HOST}:{settings.DB_PORT}...")
            # 1. Create database if it does not exist
            await self.ensure_mysql_db_exists()
            
            # 2. Establish connection pool
            self.pool = await aiomysql.create_pool(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                db=settings.DB_NAME,
                autocommit=True,
                minsize=1,
                maxsize=10
            )
            logger.info("MySQL database connection pool established.")
            await self.init_tables()
        except Exception as my_err:
            logger.warning(
                f"Failed to connect to MySQL: {my_err}. "
                f"Initializing SQLite fallback database at: {self.sqlite_path}"
            )
            self.pool = None
            self.use_sqlite = True
            await self.init_tables()

    async def disconnect(self):
        """Close connection resources."""
        if self.use_supabase:
            logger.info("Supabase client active, no connection pool to close.")
        elif self.pool:
            logger.info("Closing MySQL connection pool...")
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("MySQL connection pool closed.")
        elif self.use_sqlite:
            logger.info("SQLite connection closed (auto-handled per transaction).")

    async def init_tables(self):
        """Create tables in MySQL or SQLite."""
        if not self.use_sqlite:
            # MySQL Schema
            queries = [
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(255) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB;
                """,
                """
                CREATE TABLE IF NOT EXISTS voice_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL,
                    sequence_number INT NOT NULL,
                    audio_size_bytes INT NOT NULL,
                    transcription TEXT,
                    classification_intent VARCHAR(255),
                    classification_sentiment VARCHAR(255),
                    response_text TEXT,
                    transcription_latency_ms INT,
                    classification_latency_ms INT,
                    response_latency_ms INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB;
                """,
                """
                CREATE TABLE IF NOT EXISTS network_metrics (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL,
                    latency_ms INT,
                    packet_loss_rate FLOAT,
                    jitter_ms INT,
                    bandwidth_kbps FLOAT,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB;
                """,
                """
                CREATE TABLE IF NOT EXISTS zonas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(255) UNIQUE NOT NULL,
                    estado VARCHAR(255) NOT NULL
                ) ENGINE=InnoDB;
                """,
                """
                CREATE TABLE IF NOT EXISTS equipos_red (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(255) UNIQUE NOT NULL,
                    zona_id INT NOT NULL,
                    cpu_usage FLOAT NOT NULL,
                    mem_usage FLOAT NOT NULL,
                    packet_loss FLOAT NOT NULL,
                    interface_status VARCHAR(255) NOT NULL,
                    FOREIGN KEY (zona_id) REFERENCES zonas(id) ON DELETE CASCADE
                ) ENGINE=InnoDB;
                """,
                """
                CREATE TABLE IF NOT EXISTS clientes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(255) NOT NULL,
                    dni VARCHAR(255) UNIQUE NOT NULL,
                    router_sn VARCHAR(255) UNIQUE NOT NULL,
                    zona_id INT NOT NULL,
                    FOREIGN KEY (zona_id) REFERENCES zonas(id) ON DELETE CASCADE
                ) ENGINE=InnoDB;
                """,
                """
                CREATE TABLE IF NOT EXISTS incidencias (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL,
                    cliente_id INT NOT NULL,
                    descripcion TEXT,
                    nivel_gravedad VARCHAR(255),
                    estado VARCHAR(255),
                    creado_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES conversations(session_id) ON DELETE CASCADE,
                    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
                ) ENGINE=InnoDB;
                """,
                """
                CREATE TABLE IF NOT EXISTS reportes_tecnicos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    incidencia_id INT NOT NULL,
                    diagnostico TEXT,
                    confianza FLOAT,
                    detalles_tecnicos TEXT,
                    creado_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (incidencia_id) REFERENCES incidencias(id) ON DELETE CASCADE
                ) ENGINE=InnoDB;
                """
            ]
            seed_queries = [
                "INSERT IGNORE INTO zonas (id, nombre, estado) VALUES (1, 'Norte', 'falla_individual'), (2, 'Sur', 'operativo'), (3, 'Centro', 'falla_masiva'), (4, 'Este', 'operativo');",
                "INSERT IGNORE INTO equipos_red (id, nombre, zona_id, cpu_usage, mem_usage, packet_loss, interface_status) VALUES (1, 'Router-Norte-01', 1, 88.0, 75.0, 4.5, 'up'), (2, 'Router-Sur-01', 2, 25.0, 40.0, 0.0, 'up'), (3, 'Router-Centro-01', 3, 99.0, 95.0, 15.0, 'down'), (4, 'Router-Este-01', 4, 30.0, 45.0, 0.0, 'up');",
                "INSERT IGNORE INTO clientes (id, nombre, dni, router_sn, zona_id) VALUES (1, 'Diego Torres', '12345678', 'RT000001', 1), (2, 'Sergio Perez', '87654321', 'RT000002', 2), (3, 'Maria Gomez', '11112222', 'RT000003', 3), (4, 'Juan Lopez', '33334444', 'RT000004', 4);"
            ]
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    for query in queries:
                        await cur.execute(query)
                    for seed in seed_queries:
                        await cur.execute(seed)
            logger.info("MySQL tables checked, created, and seeded.")
        else:
            # SQLite Schema
            queries = [
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS voice_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    sequence_number INTEGER NOT NULL,
                    audio_size_bytes INTEGER NOT NULL,
                    transcription TEXT,
                    classification_intent TEXT,
                    classification_sentiment TEXT,
                    response_text TEXT,
                    transcription_latency_ms INTEGER,
                    classification_latency_ms INTEGER,
                    response_latency_ms INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS network_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    latency_ms INTEGER,
                    packet_loss_rate REAL,
                    jitter_ms INTEGER,
                    bandwidth_kbps REAL,
                    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS zonas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT UNIQUE NOT NULL,
                    estado TEXT NOT NULL
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS equipos_red (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT UNIQUE NOT NULL,
                    zona_id INTEGER NOT NULL,
                    cpu_usage REAL NOT NULL,
                    mem_usage REAL NOT NULL,
                    packet_loss REAL NOT NULL,
                    interface_status TEXT NOT NULL,
                    FOREIGN KEY (zona_id) REFERENCES zonas(id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    dni TEXT UNIQUE NOT NULL,
                    router_sn TEXT UNIQUE NOT NULL,
                    zona_id INTEGER NOT NULL,
                    FOREIGN KEY (zona_id) REFERENCES zonas(id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS incidencias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    cliente_id INTEGER NOT NULL,
                    descripcion TEXT,
                    nivel_gravedad TEXT,
                    estado TEXT,
                    creado_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES conversations(session_id) ON DELETE CASCADE,
                    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS reportes_tecnicos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incidencia_id INTEGER NOT NULL,
                    diagnostico TEXT,
                    confianza REAL,
                    detalles_tecnicos TEXT,
                    creado_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (incidencia_id) REFERENCES incidencias(id) ON DELETE CASCADE
                );
                """
            ]
            seed_queries = [
                "INSERT OR IGNORE INTO zonas (id, nombre, estado) VALUES (1, 'Norte', 'falla_individual'), (2, 'Sur', 'operativo'), (3, 'Centro', 'falla_masiva'), (4, 'Este', 'operativo');",
                "INSERT OR IGNORE INTO equipos_red (id, nombre, zona_id, cpu_usage, mem_usage, packet_loss, interface_status) VALUES (1, 'Router-Norte-01', 1, 88.0, 75.0, 4.5, 'up'), (2, 'Router-Sur-01', 2, 25.0, 40.0, 0.0, 'up'), (3, 'Router-Centro-01', 3, 99.0, 95.0, 15.0, 'down'), (4, 'Router-Este-01', 4, 30.0, 45.0, 0.0, 'up');",
                "INSERT OR IGNORE INTO clientes (id, nombre, dni, router_sn, zona_id) VALUES (1, 'Diego Torres', '12345678', 'RT000001', 1), (2, 'Sergio Perez', '87654321', 'RT000002', 2), (3, 'Maria Gomez', '11112222', 'RT000003', 3), (4, 'Juan Lopez', '33334444', 'RT000004', 4);"
            ]
            
            def _create_sqlite_tables():
                conn = sqlite3.connect(self.sqlite_path)
                try:
                    conn.execute("PRAGMA foreign_keys = ON;")
                    cursor = conn.cursor()
                    for query in queries:
                        cursor.execute(query)
                    for seed in seed_queries:
                        cursor.execute(seed)
                    conn.commit()
                finally:
                    conn.close()

            await asyncio.to_thread(_create_sqlite_tables)
            logger.info("SQLite tables checked, created, and seeded successfully.")

    async def create_conversation(self, session_id: str) -> bool:
        """Insert a new conversation session."""
        if self.use_supabase:
            try:
                def _insert():
                    return self.supabase_client.table("conversations").insert({"session_id": session_id}).execute()
                await asyncio.to_thread(_insert)
                return True
            except Exception as e:
                logger.error(f"Supabase create_conversation error: {e}")
                return False

        if self.use_sqlite:
            query = "INSERT OR IGNORE INTO conversations (session_id) VALUES (?);"
            params = (session_id,)
        else:
            query = "INSERT IGNORE INTO conversations (session_id) VALUES (%s);"
            params = (session_id,)

        return await self._execute(query, params)

    async def log_voice_interaction(
        self,
        session_id: str,
        sequence_number: int,
        audio_size_bytes: int,
        transcription: str,
        classification_intent: str,
        classification_sentiment: str,
        response_text: str,
        transcription_latency_ms: int,
        classification_latency_ms: int,
        response_latency_ms: int
    ) -> bool:
        """Insert details of an audio segment processing interaction."""
        if self.use_supabase:
            try:
                data = {
                    "session_id": session_id,
                    "sequence_number": sequence_number,
                    "audio_size_bytes": audio_size_bytes,
                    "transcription": transcription,
                    "classification_intent": classification_intent,
                    "classification_sentiment": classification_sentiment,
                    "response_text": response_text,
                    "transcription_latency_ms": transcription_latency_ms,
                    "classification_latency_ms": classification_latency_ms,
                    "response_latency_ms": response_latency_ms
                }
                def _insert():
                    return self.supabase_client.table("voice_logs").insert(data).execute()
                await asyncio.to_thread(_insert)
                return True
            except Exception as e:
                logger.error(f"Supabase log_voice_interaction error: {e}")
                return False

        if self.use_sqlite:
            query = """
            INSERT INTO voice_logs (
                session_id, sequence_number, audio_size_bytes, transcription, 
                classification_intent, classification_sentiment, response_text, 
                transcription_latency_ms, classification_latency_ms, response_latency_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """
        else:
            query = """
            INSERT INTO voice_logs (
                session_id, sequence_number, audio_size_bytes, transcription, 
                classification_intent, classification_sentiment, response_text, 
                transcription_latency_ms, classification_latency_ms, response_latency_ms
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            
        params = (
            session_id,
            sequence_number,
            audio_size_bytes,
            transcription,
            classification_intent,
            classification_sentiment,
            response_text,
            transcription_latency_ms,
            classification_latency_ms,
            response_latency_ms
        )
        return await self._execute(query, params)

    async def log_network_metrics(
        self,
        session_id: str,
        latency_ms: int,
        packet_loss_rate: float,
        jitter_ms: int,
        bandwidth_kbps: float
    ) -> bool:
        """Insert real-time network streaming diagnostics."""
        if self.use_supabase:
            try:
                data = {
                    "session_id": session_id,
                    "latency_ms": latency_ms,
                    "packet_loss_rate": packet_loss_rate,
                    "jitter_ms": jitter_ms,
                    "bandwidth_kbps": bandwidth_kbps
                }
                def _insert():
                    return self.supabase_client.table("network_metrics").insert(data).execute()
                await asyncio.to_thread(_insert)
                return True
            except Exception as e:
                logger.error(f"Supabase log_network_metrics error: {e}")
                return False

        if self.use_sqlite:
            query = """
            INSERT INTO network_metrics (
                session_id, latency_ms, packet_loss_rate, jitter_ms, bandwidth_kbps
            ) VALUES (?, ?, ?, ?, ?);
            """
        else:
            query = """
            INSERT INTO network_metrics (
                session_id, latency_ms, packet_loss_rate, jitter_ms, bandwidth_kbps
            ) VALUES (%s, %s, %s, %s, %s);
            """

        params = (session_id, latency_ms, packet_loss_rate, jitter_ms, bandwidth_kbps)
        return await self._execute(query, params)

    async def get_client_by_identifier(self, login_type: str, login_value: str) -> dict | None:
        """
        Retrieve client info by DNI or Router S/N, including their zone name and status.
        """
        if self.use_sqlite:
            query = """
            SELECT c.id, c.nombre, c.dni, c.router_sn, c.zona_id, z.nombre as zona_nombre, z.estado as zona_estado
            FROM clientes c
            JOIN zonas z ON c.zona_id = z.id
            WHERE {} = ?;
            """.format("c.dni" if login_type.upper() == "DNI" else "c.router_sn")
            params = (login_value,)
        else:
            query = """
            SELECT c.id, c.nombre, c.dni, c.router_sn, c.zona_id, z.nombre as zona_nombre, z.estado as zona_estado
            FROM clientes c
            JOIN zonas z ON c.zona_id = z.id
            WHERE {} = %s;
            """.format("c.dni" if login_type.upper() == "DNI" else "c.router_sn")
            params = (login_value,)

        def _fetch_sqlite():
            conn = sqlite3.connect(self.sqlite_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
            finally:
                conn.close()

        if self.use_sqlite:
            return await asyncio.to_thread(_fetch_sqlite)
        else:
            if not self.pool:
                return None
            try:
                async with self.pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cur:
                        await cur.execute(query, params)
                        row = await cur.fetchone()
                        return row
            except Exception as e:
                logger.error(f"MySQL get_client_by_identifier error: {e}")
                return None

    async def get_network_status_by_zone(self, zona_id: int) -> dict | None:
        """
        Get network equipment parameters for a given zone.
        """
        if self.use_sqlite:
            query = """
            SELECT nombre, cpu_usage, mem_usage, packet_loss, interface_status
            FROM equipos_red
            WHERE zona_id = ?;
            """
            params = (zona_id,)
        else:
            query = """
            SELECT nombre, cpu_usage, mem_usage, packet_loss, interface_status
            FROM equipos_red
            WHERE zona_id = %s;
            """
            params = (zona_id,)

        def _fetch_sqlite():
            conn = sqlite3.connect(self.sqlite_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
            finally:
                conn.close()

        if self.use_sqlite:
            return await asyncio.to_thread(_fetch_sqlite)
        else:
            if not self.pool:
                return None
            try:
                async with self.pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cur:
                        await cur.execute(query, params)
                        row = await cur.fetchone()
                        return row
            except Exception as e:
                logger.error(f"MySQL get_network_status_by_zone error: {e}")
                return None

    async def create_incident_and_report(
        self,
        session_id: str,
        cliente_id: int,
        descripcion: str,
        nivel_gravedad: str,
        estado: str,
        diagnostico: str,
        confianza: float,
        detalles_tecnicos: str
    ) -> int | None:
        """
        Inserts an incident and its corresponding technical report, returning the incident ID.
        """
        if self.use_sqlite:
            inc_query = """
            INSERT INTO incidencias (session_id, cliente_id, descripcion, nivel_gravedad, estado)
            VALUES (?, ?, ?, ?, ?);
            """
            inc_params = (session_id, cliente_id, descripcion, nivel_gravedad, estado)
            
            rep_query = """
            INSERT INTO reportes_tecnicos (incidencia_id, diagnostico, confianza, detalles_tecnicos)
            VALUES (?, ?, ?, ?);
            """
            
            def _insert_sqlite():
                conn = sqlite3.connect(self.sqlite_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute(inc_query, inc_params)
                    inc_id = cursor.lastrowid
                    cursor.execute(rep_query, (inc_id, diagnostico, confianza, detalles_tecnicos))
                    conn.commit()
                    return inc_id
                except Exception as e:
                    logger.error(f"SQLite create_incident_and_report error: {e}")
                    return None
                finally:
                    conn.close()
                    
            return await asyncio.to_thread(_insert_sqlite)
        else:
            if not self.pool:
                return None
            try:
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        inc_query = """
                        INSERT INTO incidencias (session_id, cliente_id, descripcion, nivel_gravedad, estado)
                        VALUES (%s, %s, %s, %s, %s);
                        """
                        inc_params = (session_id, cliente_id, descripcion, nivel_gravedad, estado)
                        await cur.execute(inc_query, inc_params)
                        inc_id = conn.insert_id()
                        
                        rep_query = """
                        INSERT INTO reportes_tecnicos (incidencia_id, diagnostico, confianza, detalles_tecnicos)
                        VALUES (%s, %s, %s, %s);
                        """
                        await cur.execute(rep_query, (inc_id, diagnostico, confianza, detalles_tecnicos))
                        return inc_id
            except Exception as e:
                logger.error(f"MySQL create_incident_and_report error: {e}")
                return None

    async def _execute(self, query: str, params: tuple) -> bool:
        """Helper to run DB updates on MySQL or SQLite."""
        if not self.pool and not self.use_sqlite:
            logger.error("No active database engine available.")
            return False

        if self.use_sqlite:
            def _run_sqlite():
                conn = sqlite3.connect(self.sqlite_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute(query, params)
                    conn.commit()
                    return True
                except Exception as e:
                    logger.error(f"SQLite transaction error: {e}")
                    return False
                finally:
                    conn.close()

            return await asyncio.to_thread(_run_sqlite)
        else:
            # MySQL Pool update
            try:
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(query, params)
                return True
            except Exception as e:
                logger.error(f"MySQL transaction error: {e}")
                return False

db = DatabaseManager()


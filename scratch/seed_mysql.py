import asyncio
import sys
import pathlib
import aiomysql

# Add backend to path
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

from backend.config import settings

# Define the seed queries
seed_queries = [
    """INSERT IGNORE INTO zonas (id, nombre, estado) VALUES 
       (1, 'Norte', 'falla_individual'), 
       (2, 'Sur', 'operativo'), 
       (3, 'Centro', 'falla_masiva'), 
       (4, 'Este', 'operativo'),
       (5, 'Oeste', 'operativo'),
       (6, 'Rural', 'falla_individual');""",
    """INSERT IGNORE INTO equipos_red (id, nombre, zona_id, cpu_usage, mem_usage, packet_loss, interface_status) VALUES 
       (1, 'Router-Norte-01', 1, 88.0, 75.0, 4.5, 'up'), 
       (2, 'Router-Sur-01', 2, 25.0, 40.0, 0.0, 'up'), 
       (3, 'Router-Centro-01', 3, 99.0, 95.0, 15.0, 'down'), 
       (4, 'Router-Este-01', 4, 30.0, 45.0, 0.0, 'up'),
       (5, 'Router-Norte-02', 1, 35.0, 42.0, 1.2, 'up'),
       (6, 'Router-Sur-02', 2, 45.0, 50.0, 3.0, 'up'),
       (7, 'Router-Centro-02', 3, 10.0, 15.0, 100.0, 'down'),
       (8, 'Router-Este-02', 4, 28.0, 35.0, 0.0, 'up'),
       (9, 'Router-Oeste-01', 5, 0.0, 0.0, 100.0, 'down'),
       (10, 'Router-Oeste-02', 5, 0.0, 0.0, 100.0, 'down'),
       (11, 'Router-Rural-01', 6, 40.0, 45.0, 50.0, 'up'),
       (12, 'Router-Norte-03', 1, 95.0, 88.0, 2.5, 'up'),
       (13, 'Router-Sur-03', 2, 60.0, 55.0, 0.5, 'up'),
       (14, 'Router-Centro-03', 3, 0.0, 0.0, 100.0, 'down'),
       (15, 'Router-Este-03', 4, 32.0, 40.0, 0.0, 'up'),
       (16, 'Router-Oeste-03', 5, 75.0, 80.0, 20.0, 'up'),
       (17, 'Router-Rural-02', 6, 20.0, 30.0, 80.0, 'up'),
       (18, 'Router-Norte-04', 1, 42.0, 48.0, 1.8, 'up'),
       (19, 'Router-Sur-04', 2, 30.0, 40.0, 0.0, 'up'),
       (20, 'Router-Centro-04', 3, 50.0, 60.0, 40.0, 'up'),
       (21, 'Router-Este-04', 4, 25.0, 35.0, 90.0, 'up'),
       (22, 'Router-Oeste-04', 5, 10.0, 15.0, 100.0, 'down'),
       (23, 'Router-Rural-03', 6, 0.0, 0.0, 100.0, 'down'),
       (24, 'Router-Sur-05', 2, 85.0, 78.0, 15.0, 'up');""",
    """INSERT IGNORE INTO clientes (id, nombre, dni, router_sn, zona_id) VALUES 
       (1, 'Diego Torres', '12345678', 'RT000001', 1), 
       (2, 'Sergio Perez', '87654321', 'RT000002', 2), 
       (3, 'Maria Gomez', '11112222', 'RT000003', 3), 
       (4, 'Juan Lopez', '33334444', 'RT000004', 4),
       (5, 'Luis Alberto', '20202020', 'RT000005', 1),
       (6, 'Ana Benites', '30303030', 'RT000006', 2),
       (7, 'Carlos Mendoza', '40404040', 'RT000007', 3),
       (8, 'Sofia Rojas', '50505050', 'RT000008', 4),
       (9, 'Javier Prado', '60606060', 'RT000009', 5),
       (10, 'Elena Rivas', '70707070', 'RT000010', 5),
       (11, 'Pedro Gomez', '80808080', 'RT000011', 6),
       (12, 'Rosa Peralta', '90909090', 'RT000012', 1),
       (13, 'Miguel Angel', '12121212', 'RT000013', 2),
       (14, 'Carmen Rosa', '34343434', 'RT000014', 3),
       (15, 'Jorge Chavez', '56565656', 'RT000015', 4),
       (16, 'Patricia Sanz', '78787878', 'RT000016', 5),
       (17, 'Fernando Ruiz', '90123456', 'RT000017', 6),
       (18, 'Lucia Castro', '89012345', 'RT000018', 1),
       (19, 'Victor Hugo', '78901234', 'RT000019', 2),
       (20, 'Gabriela Paz', '67890123', 'RT000020', 3),
       (21, 'Ricardo Gareca', '56789012', 'RT000021', 4),
       (22, 'Monica Sanchez', '45678901', 'RT000022', 5),
       (23, 'Raul Ruidiaz', '34567890', 'RT000023', 6),
       (24, 'Vanessa Terkes', '23456789', 'RT000024', 2);"""
]

async def run_seed():
    print(f"Connecting to MySQL XAMPP at {settings.DB_HOST}:{settings.DB_PORT}...")
    try:
        conn = await aiomysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            db=settings.DB_NAME,
            autocommit=True
        )
        print("Connected! Seeding 'miranet_db' tables...")
        async with conn.cursor() as cur:
            for seed in seed_queries:
                await cur.execute(seed)
        conn.close()
        print("Successfully seeded all 24 clients, red equipment, and zones in MySQL XAMPP database!")
    except Exception as e:
        print(f"Error seeding MySQL database: {e}")
        print("Asegúrate de que el panel de XAMPP de MySQL esté encendido en el puerto 3307.")

if __name__ == "__main__":
    asyncio.run(run_seed())

import asyncio
import sys
import pathlib

# Add backend to path
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

from backend.db.database import db

async def verify():
    print("Connecting to database manager...")
    await db.connect()
    
    # Query client count
    if db.use_sqlite:
        import sqlite3
        conn = sqlite3.connect(db.sqlite_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM clientes;")
        count = cursor.fetchone()[0]
        print(f"[SQLite] Total Clients: {count}")
        cursor.execute("SELECT id, nombre, dni, router_sn, zona_id FROM clientes;")
        for row in cursor.fetchall():
            print(f"  - {row}")
        conn.close()
    else:
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) FROM clientes;")
                count = (await cur.fetchone())[0]
                print(f"[MySQL] Total Clients: {count}")
                await cur.execute("SELECT id, nombre, dni, router_sn, zona_id FROM clientes;")
                for row in await cur.fetchall():
                    print(f"  - {row}")
                    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(verify())

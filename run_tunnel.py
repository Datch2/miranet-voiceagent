import subprocess
import re
import sys
import os
import time
from pyngrok import ngrok
from dotenv import load_dotenv

def main():
    print("=================================================================")
    print("     Miranet VoiceAgent - Inicio Automático de Túnel Ngrok      ")
    print("=================================================================")
    
    # Cargar variables de entorno
    load_dotenv(dotenv_path=".env")
    authtoken = os.getenv("NGROK_AUTHTOKEN", "").strip()
    
    if authtoken:
        print("🔑 Token de autenticación de ngrok cargado desde .env.")
        ngrok.set_auth_token(authtoken)
    else:
        print("⚠️ Advertencia: No se encontró NGROK_AUTHTOKEN configurado en el archivo .env.")
        print("Si ngrok requiere autenticación, por favor edita tu archivo .env y coloca tu token.")

    # 1. Iniciar el servidor backend FastAPI
    print("\n[1/4] Iniciando servidor FastAPI local en puerto 8000...")
    backend_proc = subprocess.Popen(
        [sys.executable, "backend/main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Esperar a que inicie el servidor
    time.sleep(3)
    if backend_proc.poll() is not None:
        print("❌ Error: El servidor backend no pudo iniciar.")
        stdout, stderr = backend_proc.communicate()
        print(stderr)
        return
    print("✅ Servidor backend corriendo localmente en el puerto 8000.")

    # 2. Iniciar el túnel público usando pyngrok
    print("\n[2/4] Creando túnel de red pública con ngrok...")
    try:
        # Conectar el túnel de ngrok en el puerto 8000
        tunnel = ngrok.connect(8000)
        url = tunnel.public_url
    except Exception as e:
        print(f"❌ Error al crear el túnel de ngrok: {e}")
        print("\nPara solucionar esto:")
        print("1. Regístrate gratis en https://dashboard.ngrok.com/")
        print("2. Copia tu Auth Token de la consola de ngrok.")
        print("3. Agrégalo a tu archivo .env en la línea: NGROK_AUTHTOKEN=tu_token_aqui")
        backend_proc.terminate()
        return

    print(f"✅ ¡Túnel creado con éxito!: {url}")

    # 3. Actualizar dinámicamente frontend/index.js con la nueva URL
    js_path = os.path.join("frontend", "index.js")
    print(f"\n[3/4] Actualizando constante en '{js_path}'...")
    try:
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Reemplazar la línea de TUNNEL_URL con la nueva dirección
        new_content = re.sub(
            r'const TUNNEL_URL = "[^"]*";',
            f'const TUNNEL_URL = "{url}";',
            content
        )
        
        with open(js_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print("✅ Archivo 'frontend/index.js' actualizado con la URL del túnel.")
    except Exception as e:
        print(f"❌ Error al escribir en el archivo JavaScript: {e}")

    # 4. Mostrar instrucciones finales
    print("\n=================================================================")
    print("                     🏁 INSTRUCCIONES FINALES                     ")
    print("=================================================================")
    print("1. Para actualizar tu GitHub Pages con esta nueva URL, haz:")
    print("   git add frontend/index.js")
    print("   git commit -m \"Actualizar URL temporal de túnel\"")
    print("   git push")
    print(f"2. Abre tu enlace de GitHub Pages en cualquier red móvil o WiFi.")
    print("3. Presiona CTRL+C en esta terminal para apagar el servidor y el túnel.")
    print("=================================================================\n")

    try:
        # Mantener los procesos vivos monitoreando
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[4/4] Apagando el servidor local y cerrando el túnel...")
        backend_proc.terminate()
        try:
            ngrok.disconnect(tunnel.public_url)
            ngrok.kill()
        except Exception:
            pass
        print("👋 Todos los procesos finalizados correctamente.")

if __name__ == "__main__":
    main()

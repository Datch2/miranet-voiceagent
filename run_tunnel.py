import subprocess
import re
import sys
import os
import time

def main():
    print("=================================================================")
    print("     Miranet VoiceAgent - Inicio Automático de Túnel Local      ")
    print("=================================================================")
    
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

    # 2. Iniciar el túnel público usando localtunnel
    print("\n[2/4] Creando túnel de red pública con localtunnel (npx localtunnel)...")
    try:
        # En Windows npx se ejecuta como npx.cmd
        npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
        tunnel_proc = subprocess.Popen(
            [npx_cmd, "localtunnel", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
    except FileNotFoundError:
        print("❌ Error: No se encontró 'npx' o 'Node.js' instalado.")
        print("Por favor, asegúrate de tener Node.js instalado en tu máquina para usar 'npx'.")
        backend_proc.terminate()
        return

    # 3. Leer la salida del túnel para extraer la URL pública
    url = None
    print("⏳ Esperando respuesta del servidor de túneles...")
    
    # Leemos la salida de localtunnel línea por línea
    start_time = time.time()
    while time.time() - start_time < 15:  # Tiempo de espera máximo de 15 segundos
        line = tunnel_proc.stdout.readline()
        if not line:
            break
        line_str = line.strip()
        print(f"   > {line_str}")
        
        # Buscar el patrón "your url is: https://..."
        match = re.search(r"your url is:\s*(https?://[^\s]+)", line_str)
        if match:
            url = match.group(1)
            break

    if not url:
        print("❌ Error: No se pudo obtener la URL pública de localtunnel.")
        backend_proc.terminate()
        tunnel_proc.terminate()
        return

    print(f"✅ ¡Túnel creado con éxito!: {url}")

    # 4. Actualizar dinámicamente frontend/index.js con la nueva URL
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

    # 5. Mostrar instrucciones finales
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
        tunnel_proc.terminate()
        print("👋 Todos los procesos finalizados correctamente.")

if __name__ == "__main__":
    main()

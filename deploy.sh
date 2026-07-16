#!/bin/bash
echo "================================================================="
echo "       MIRANET VOICEAGENT - AUTOMATED CLOUD DEPLOYMENT"
echo "================================================================="

# 1. Start Docker Containers in production mode
echo "🚀 Starting Docker Compose containers..."
docker compose -f docker-compose.prod.yml up -d

# 2. Wait for MySQL to be ready
echo "⏳ Waiting for MySQL Database container to be fully initialized..."
until docker exec miranet-mysql-db mysql -uroot -pMiranetSecureDb2026! -e "select 1;" &>/dev/null; do
    sleep 2
done
echo "✅ MySQL Database is ready for connections!"

# 3. Create databases if not exists
echo "🗄️ Initializing MySQL databases..."
docker exec -i miranet-mysql-db mysql -uroot -pMiranetSecureDb2026! -e "CREATE DATABASE IF NOT EXISTS cacti; CREATE DATABASE IF NOT EXISTS miranet_db;"

# 4. Import Cacti schema dump
if [ -f "cacti_full.sql" ]; then
    echo "📥 Importing Cacti system tables (cacti_full.sql)..."
    docker exec -i miranet-mysql-db mysql -uroot -pMiranetSecureDb2026! cacti < cacti_full.sql
    echo "✅ Cacti schema imported successfully!"
else
    echo "⚠️ Warning: cacti_full.sql not found in current directory. Skipping import."
fi

# 5. Fix Cacti Log path mapping inside the container database
echo "🛠️ Fixing Cacti log path settings for Linux filesystem..."
docker exec -i miranet-mysql-db mysql -uroot -pMiranetSecureDb2026! cacti -e "UPDATE settings SET value = '/var/www/html/cacti/log/cacti.log' WHERE name = 'path_cactilog';"

# 6. Wait for Ollama service to be ready
echo "⏳ Waiting for Ollama AI engine to start..."
until curl -s http://localhost:11434/api/tags &>/dev/null; do
    sleep 2
done
echo "✅ Ollama is active!"

# 7. Pull the phi3 LLM model inside the container
echo "🧠 Downloading phi3 model (this may take a couple of minutes depending on network speed)..."
docker exec -i miranet-ollama ollama pull phi3
echo "✅ phi3 model is loaded and ready!"

# 8. Restart voice agent container to ensure it connects cleanly to database and Ollama
echo "🔄 Restarting Miranet Voice Agent container..."
docker restart miranet-voice-agent

echo "================================================================="
echo " 🎉 CLOUD DEPLOYMENT COMPLETE!"
echo "================================================================="
echo " Client Web Portal: http://<YOUR_DROPLET_IP>:8000/"
echo " Cacti Telemetry Dashboard: http://<YOUR_DROPLET_IP>:8080/cacti/"
echo "================================================================="

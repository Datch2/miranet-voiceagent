FROM python:3.10-slim

# Install system dependencies (ffmpeg is required by Whisper to process audio files!)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install dependencies (use pip cache)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

EXPOSE 8000

# Start FastAPI server
CMD ["python", "backend/main.py"]

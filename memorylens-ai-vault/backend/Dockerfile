FROM python:3.12-slim

# System libs opencv-python-headless and faster-whisper (via ffmpeg) need
# at runtime -- without these the container boots but every upload fails
# with a native import/codec error.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Not baked into the image: real uploads, thumbnails, keyframes, and the
# SQLite DB. docker-compose mounts ./data as a volume over this so a
# container restart/rebuild never loses the vault.
RUN mkdir -p data/uploads data/thumbnails data/keyframes

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

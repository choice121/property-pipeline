FROM python:3.11-slim

WORKDIR /app

# ── System packages (Pillow native libs + Node.js 20) ─────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl gnupg \
    libfreetype6-dev libjpeg-dev libpng-dev libwebp-dev \
    libtiff-dev libopenjp2-7-dev zlib1g-dev \
  && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
  && apt-get install -y nodejs \
  && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ────────────────────────────────────────────────────────
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# ── Frontend dependencies ──────────────────────────────────────────────────────
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm install --silent

# ── Copy full source ───────────────────────────────────────────────────────────
COPY . .

# ── Persistent data volumes ───────────────────────────────────────────────────
RUN mkdir -p backend/storage/images backend/data

ENV PYTHONUNBUFFERED=1

EXPOSE 5000 8000

CMD ["bash", "start.sh"]

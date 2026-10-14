# Dockerfile for EcoPackAI backend (Flask)
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed by psycopg2 / scientific libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better layer caching)
COPY environments/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual application code
COPY backend/ ./backend/
COPY ml/ ./ml/
# The API also needs the predictor/ranking code, the ranking config and the
# material catalogue (used to scale scores like the ranking engine)
COPY src/ ./src/
COPY config/ ./config/
COPY data/processed/ ./data/processed/

# Listen on all interfaces inside the container; no debug mode
ENV APP_HOST=0.0.0.0 \
    APP_PORT=5000 \
    APP_ENV=production

WORKDIR /app/backend

EXPOSE 5000

# Create/upgrade the tables and load the CSVs (safe to repeat), then start the API
CMD ["sh", "-c", "python manage.py init-db && python app.py"]

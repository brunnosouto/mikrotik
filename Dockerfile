FROM python:3.11-slim

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Hugging Face Spaces runs as user 1000. 
# We grant full read/write/execute permissions to the app directory to allow SQLite to write telemetry.db.
RUN chmod -R 777 /app

EXPOSE 8000

# Run with Gunicorn, binding to the PORT environment variable (defaulting to 8000) with 1 worker to prevent database locks on SQLite.
CMD gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 1 app:app

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install core server packages first (guaranteed)
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    pydantic \
    pydantic-settings \
    python-dotenv \
    supabase \
    celery \
    redis \
    boto3 \
    "python-jose[cryptography]" \
    httpx \
    cryptography

# Copy and install any remaining deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

# Copy all backend code
COPY . .

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

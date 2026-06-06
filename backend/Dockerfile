FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install all dependencies directly (bypasses any requirements.txt cache issues)
RUN pip install --no-cache-dir \
    "fastapi>=0.111.0" \
    "uvicorn[standard]>=0.29.0" \
    "supabase>=2.4.0" \
    "celery>=5.3.6" \
    "redis>=5.0.3" \
    "boto3>=1.34.0" \
    "python-jose[cryptography]>=3.3.0" \
    "httpx>=0.27.0" \
    "python-dotenv>=1.0.0" \
    "pydantic>=2.6.0" \
    "pydantic-settings>=2.2.0" \
    "cryptography>=42.0.0"

COPY . .

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

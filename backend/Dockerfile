FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    imagemagick \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app

# Install all backend dependencies directly
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

# Install agent pipeline dependencies (script/voiceover/video generation)
RUN pip install --no-cache-dir \
    "anthropic>=0.25.0" \
    "elevenlabs>=1.2.0" \
    "requests>=2.31.0" \
    "moviepy==1.0.3" \
    "google-api-python-client>=2.100.0" \
    "google-auth-httplib2>=0.1.1" \
    "google-auth-oauthlib>=1.1.0" \
    "Pillow>=10.0.0" \
    "numpy>=1.24.0" \
    "tqdm>=4.66.0"

# Copy ONLY backend/ into /app — keeps root main.py (CLI tool) out
COPY backend/ /app/

# Copy agent pipeline modules into /agent (config.py renamed to avoid
# clashing with backend's config.py)
COPY script_generator.py voiceover.py video_creator.py youtube_uploader.py /agent/
COPY config.py /agent/agent_config.py

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.11-slim

# Install system dependencies with proper directory handling
RUN mkdir -p /var/lib/apt/lists/partial && \
    apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER appuser

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
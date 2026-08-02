FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create models and generated_audio directories
RUN mkdir -p /app/models /app/generated_audio

# Set Python path
ENV PYTHONPATH=/app

# Expose port
EXPOSE 2002

# Run uvicorn on port 2002
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "2002"]

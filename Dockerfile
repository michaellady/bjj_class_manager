FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libsqlite3-dev \
    curl \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies needed by torchreid
RUN pip install --no-cache-dir gdown tensorboard
RUN pip install --no-cache-dir torch torchvision
RUN pip install --no-cache-dir torchreid

# Install other requirements
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p pictures/incoming \
    data/face_crops \
    data/representative_features \
    data/representative_persons

# Expose port
EXPOSE 5001

# Create a startup script to initialize the database and start the app
RUN echo '#!/bin/bash\npython -c "from src.database_setup import initialize_database; initialize_database()"\npython -m flask run --host=0.0.0.0 --port=5001' > /app/start.sh && chmod +x /app/start.sh

# Run the application
ENV PYTHONPATH=/app
CMD ["/app/start.sh"] 
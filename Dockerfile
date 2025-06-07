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
    net-tools \
    iputils-ping \
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

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=src.app
ENV FLASK_DEBUG=1
ENV REQUESTS_TIMEOUT=300
ENV INSTAGRAM_TIMEOUT=180

# Make the database directory writable
RUN chmod -R 777 .

# Expose port
EXPOSE 5001

# Create a startup script to initialize the database and start the app
RUN echo '#!/bin/bash\n\
echo "Testing network connectivity..."\n\
ping -c 3 instagram.com || echo "Warning: Cannot ping Instagram (expected in containers)"\n\
curl -I https://www.instagram.com || echo "Warning: Cannot connect to Instagram (may be rate limited)"\n\
echo "Initializing database..."\n\
python -m src.database_setup\n\
if [ $? -ne 0 ]; then\n\
    echo "Database initialization failed!"\n\
    exit 1\n\
fi\n\
echo "Checking database..."\n\
ls -la *.db || echo "No .db files found in root directory"\n\
echo "Starting Flask application with extended timeouts..."\n\
python -m flask run --host=0.0.0.0 --port=5001\n\
' > /app/start.sh && chmod +x /app/start.sh

# Run the application
CMD ["/app/start.sh"] 
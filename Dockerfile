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

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=src.app
ENV FLASK_DEBUG=1

# Expose port
EXPOSE 5001

# Create a startup script to initialize the database and start the app
RUN echo '#!/bin/bash\n\
echo "Initializing database..."\n\
python -c "from src.database_setup import initialize_database; initialize_database()"\n\
echo "Starting Flask application..."\n\
python -m flask run --host=0.0.0.0 --port=5001\n\
' > /app/start.sh && chmod +x /app/start.sh

# Run the application
CMD ["/app/start.sh"] 
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libsqlite3-dev \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies needed by torchreid
RUN pip install --no-cache-dir gdown tensorboard

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
RUN echo '#!/bin/bash\n\
echo "Initializing database..."\n\
python -c "from src.database_setup import initialize_database; initialize_database()"\n\
if [ $? -ne 0 ]; then\n\
  echo "Database initialization failed!"\n\
  exit 1\n\
fi\n\
echo "Starting Flask app..."\n\
python -m flask run --host=0.0.0.0 --port=5001\n\
' > /app/start.sh && chmod +x /app/start.sh

# Run the application
ENV PYTHONPATH=/app
CMD ["/app/start.sh"] 
# BJJ Class Pictures Manager

A system for managing Brazilian Jiu-Jitsu class attendance using facial recognition from class photos.

## Features

- Process class photos to identify students using facial recognition
- Track attendance over time
- Containerized application for easy deployment
- Web interface for reviewing and managing attendance data

## Setup

### Prerequisites

- Python 3.10+
- Docker and Docker Compose (for containerized deployment)
- Required system libraries: libsqlite3-dev, libgl1-mesa-glx, libglib2.0-0, libsm6, libxext6, libxrender-dev

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/class_pictures.git
   cd class_pictures
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Initialize the database:
   ```bash
   python -c "from src.database_setup import initialize_database; initialize_database()"
   ```

### Running with Docker

Build and start the containers:
```bash
docker compose build
docker compose up
```

## Development

### Running Tests

```bash
python -m unittest discover -s src -p "test_*.py"
```

### Docker Testing

```bash
docker compose up test
```

## CI/CD Pipeline

This project uses GitHub Actions for continuous integration and deployment:

### Workflow Stages

1. **Build and Test**:
   - Sets up Python environment
   - Installs dependencies
   - Initializes the database
   - Runs unit tests
   - Builds Docker images
   - Creates application package

2. **Artifacts**:
   - Docker images are saved and uploaded as artifacts
   - Application package is created and uploaded as an artifact

3. **Deployment** (on main branch only):
   - Downloads artifacts
   - Sets up Docker images
   - Tags images for deployment
   - Creates releases for tagged commits

### Workflow Triggers

- **Pull Requests**: Builds and tests code
- **Push to Main**: Builds, tests, and prepares for deployment
- **Tags**: Creates GitHub releases with artifacts

## License

[MIT License](LICENSE)
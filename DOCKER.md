# Docker Deployment Guide

This guide provides detailed instructions for running the ServiceNow Architecture Diagram Generator using Docker.

## Why Docker?

Docker provides a containerized environment that includes all dependencies (Python, Node.js, Java) pre-configured. This means:
- ✅ No manual installation of Python, Node.js, or Java
- ✅ Consistent environment across all platforms (Windows, macOS, Linux)
- ✅ Easy deployment and updates
- ✅ Isolated from your system dependencies

## Prerequisites

### Required
- **Docker Desktop** - [Download and install Docker Desktop](https://www.docker.com/products/docker-desktop)
  - Windows: Docker Desktop for Windows
  - macOS: Docker Desktop for Mac
  - Linux: Docker Engine + Docker Compose

### Verify Docker Installation
```bash
docker --version
docker-compose --version
```

You should see version numbers for both commands.

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/leojacinto/project-virgil.git
cd project-virgil
```

### 2. Set Up Environment Variables
```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file with your API keys
nano .env  # or use your preferred text editor
```

Add at least one LLM API key:
```env
# Choose one or more:
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
GOOGLE_API_KEY=your-google-api-key-here

# Optional: Web search
SERPAPI_KEY=your-serpapi-key-here
```

### 3. Add ServiceNow JDBC Driver
```bash
# Create the jdbc directory
mkdir -p backend/jdbc

# Download the ServiceNow JDBC driver from ServiceNow Store or your instance
# Then copy it to the jdbc directory
cp /path/to/your-downloaded-jdbc-driver.jar backend/jdbc/ServiceNowJdbc-1.0.3-SNAPSHOT.jar
```

**Note:** You must obtain the ServiceNow JDBC driver from:
- Your ServiceNow instance's JDBC driver download page
- ServiceNow Store
- Contact your ServiceNow administrator

The driver is not included in this repository due to licensing restrictions.

### 4. Start the Application
```bash
# Build and start all services
docker-compose up -d

# View logs (optional)
docker-compose logs -f
```

### 5. Access the Application
- **Frontend UI:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs

### 6. Stop the Application
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (clears data)
docker-compose down -v
```

## Docker Commands Reference

### Basic Operations
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend
docker-compose logs -f frontend

# Restart services
docker-compose restart

# Rebuild containers (after code changes)
docker-compose up -d --build
```

### Troubleshooting Commands
```bash
# Check service status
docker-compose ps

# Check container health
docker ps

# Enter backend container shell
docker-compose exec backend bash

# Enter frontend container shell
docker-compose exec frontend sh

# View backend logs
docker-compose logs backend

# Remove all containers and start fresh
docker-compose down
docker-compose up -d --build
```

## Configuration

### Environment Variables

The `.env` file contains all configuration. Key variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | One LLM key required |
| `ANTHROPIC_API_KEY` | Anthropic API key | One LLM key required |
| `GOOGLE_API_KEY` | Google Gemini API key | One LLM key required |
| `SERPAPI_KEY` | SerpAPI for web search | Optional |

### Volumes

Docker Compose mounts these directories:
- `./backend/jdbc` → Container JDBC drivers
- `./backend/documents` → Uploaded documents

These persist even when containers are stopped.

## Updating the Application

### Pull Latest Changes
```bash
# Stop services
docker-compose down

# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose up -d --build
```

## Production Deployment

### Using Pre-built Images (Recommended)

For production, build images once and deploy:

```bash
# Build images
docker-compose build

# Tag images
docker tag project-virgil-backend:latest your-registry/project-virgil-backend:v1.0
docker tag project-virgil-frontend:latest your-registry/project-virgil-frontend:v1.0

# Push to registry
docker push your-registry/project-virgil-backend:v1.0
docker push your-registry/project-virgil-frontend:v1.0

# On production server, pull and run
docker-compose -f docker-compose.prod.yml up -d
```

### Environment-Specific Configuration

Create separate compose files:
- `docker-compose.yml` - Development
- `docker-compose.prod.yml` - Production

Production example:
```yaml
version: '3.8'
services:
  backend:
    image: your-registry/project-virgil-backend:v1.0
    restart: always
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    # ... other production settings
```

## Troubleshooting

### Port Already in Use
```bash
# Change ports in docker-compose.yml
ports:
  - "8001:8000"  # Backend
  - "3001:3000"  # Frontend
```

### Container Won't Start
```bash
# Check logs
docker-compose logs backend

# Rebuild from scratch
docker-compose down -v
docker-compose up -d --build
```

### Permission Issues (Linux)
```bash
# Fix file permissions
sudo chown -R $USER:$USER backend/jdbc
sudo chown -R $USER:$USER backend/documents
```

### Out of Disk Space
```bash
# Clean up unused Docker resources
docker system prune -a

# Remove old images
docker image prune -a
```

## FAQ

**Q: Do I need to install Python, Node.js, or Java?**  
A: No! Docker containers include all dependencies.

**Q: Can I run this on Windows?**  
A: Yes! Docker Desktop works on Windows 10/11 with WSL2.

**Q: How do I update to the latest version?**  
A: Run `git pull` then `docker-compose up -d --build`.

**Q: Where are my uploaded documents stored?**  
A: In `backend/documents/` directory, which persists outside containers.

**Q: Can I use this in production?**  
A: Yes! See the Production Deployment section above.

**Q: How do I backup my data?**  
A: Copy the `backend/documents/` and `backend/jdbc/` directories.

## Support

For issues:
1. Check logs: `docker-compose logs -f`
2. Verify environment variables in `.env`
3. Ensure JDBC driver is in `backend/jdbc/`
4. Open an issue on GitHub

## Next Steps

After starting the application:
1. Open http://localhost:3000
2. Configure your LLM provider (OpenAI/Anthropic/Google)
3. Connect to your ServiceNow instance
4. Upload reference documents (optional)
5. Start generating architectures!

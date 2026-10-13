.PHONY: test run build clean docker-up docker-down

# Run pytest on golden test suite
test:
	pytest tests/ -v

# Run local development server
run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Build Docker images
build:
	docker compose build

# Start services via Docker Compose
docker-up:
	docker compose up -d

# Stop services
docker-down:
	docker compose down

# Clean python cache
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

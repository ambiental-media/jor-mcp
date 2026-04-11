.PHONY: check run

# Run all code quality validations
check:
	@echo "[1/4] Linting (Ruff)..."
	uv run ruff check .
	@echo "[2/4] Formatting (Ruff)..."
	uv run ruff format --check .
	@echo "[3/4] Type Checks (MyPy)..."
	uv run mypy .
	@echo "[4/4] Tests + Coverage (Pytest)..."
	uv run pytest --cov=src --cov-fail-under=90
	@echo "All checks passed."

# Build and run the Docker container locally
run:
	@echo "Building Docker image..."
	docker build -t jor-mcp:latest .
	@echo "Running Docker container..."
	docker run --rm -p 8080:8080 --env-file .env jor-mcp:latest

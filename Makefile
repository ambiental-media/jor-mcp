.PHONY: check run

# Run all code quality validations
check:
	@echo "--- 🔍 Running Linting (Ruff) ---"
	uv run ruff check .
	@echo "--- 🎨 Checking Formatting (Ruff) ---"
	uv run ruff format --check .
	@echo "--- 🛡️ Running Type Checks (MyPy) ---"
	uv run mypy .
	@echo "--- 🧪 Running Tests & Coverage (Pytest) ---"
	uv run pytest --cov=src --cov-fail-under=90
	@echo "✅ All checks passed successfully!"

# Build and run the Docker container locally
run:
	@echo "--- 🐳 Building Docker Image ---"
	docker build -t jor-mcp:latest .
	@echo "--- 🚀 Running Docker Container ---"
	docker run --rm -p 8080:8080 --env-file .env jor-mcp:latest

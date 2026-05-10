.PHONY: check check-sast check-deps check-container run

# Run all code quality validations
check:
	@echo "[1/7] Linting (Ruff)..."
	uv run ruff check .
	@echo "[2/7] Formatting (Ruff)..."
	uv run ruff format --check .
	@echo "[3/7] Type Checks (MyPy)..."
	uv run mypy .
	@echo "[4/7] Tests + Coverage (Pytest)..."
	uv run pytest --cov=src --cov-fail-under=90
	@echo "[5/7] SAST (Bandit)..."
	uv run bandit -c pyproject.toml -r src/
	@echo "[6/7] Dependency Audit (pip-audit)..."
	uv export --no-hashes --all-groups -o requirements-ci.txt
	uv run pip-audit -r requirements-ci.txt --no-deps --disable-pip
	@echo "[7/7] Container Scan (Trivy)..."
	docker build -t jor-mcp:latest .
	trivy image --exit-code 1 --severity HIGH,CRITICAL --vuln-type library jor-mcp:latest
	@echo "All checks passed."

# SAST: static analysis for security issues in source code
check-sast:
	uv run bandit -c pyproject.toml -r src/

# SCA: audit dependencies for known vulnerabilities
check-deps:
	uv export --no-hashes --all-groups -o requirements-ci.txt
	uv run pip-audit -r requirements-ci.txt --no-deps --disable-pip

# Container scan: scan the Docker image for vulnerabilities
check-container:
	docker build -t jor-mcp:latest .
	trivy image --exit-code 1 --severity HIGH,CRITICAL --vuln-type library jor-mcp:latest

# Build and run the Docker container locally
run:
	@echo "Building Docker image..."
	docker build -t jor-mcp:latest .
	@echo "Running Docker container..."
	docker run --rm -p 8080:8080 --env-file .env jor-mcp:latest

.PHONY: check check-lint check-format check-types check-tests check-sast check-deps check-container check-portal check-docs run _audit-fail-hint

# Run all code quality validations
check:
	@echo "[1/7] Linting (Ruff)..."
	@$(MAKE) check-lint
	@echo "[2/7] Formatting (Ruff)..."
	@$(MAKE) check-format
	@echo "[3/7] Type Checks (MyPy)..."
	@$(MAKE) check-types
	@echo "[4/7] Tests + Coverage (Pytest)..."
	@$(MAKE) check-tests
	@echo "[5/7] SAST (Bandit)..."
	@$(MAKE) check-sast
	@echo "[6/7] Dependency Audit (pip-audit)..."
	@$(MAKE) check-deps
	@echo "[7/7] Container Scan (Trivy)..."
	@$(MAKE) check-container
	@echo "All checks passed."

# Code Quality: Linting
check-lint:
	uv run ruff check .

# Code Quality: Formatting
check-format:
	uv run ruff format --check .

# Code Quality: Static Type Checking
check-types:
	uv run mypy .

# Testing: Unit tests and coverage
check-tests:
	uv run pytest --cov=src --cov-fail-under=90

# Security: Static analysis for issues in source code
check-sast:
	uv run bandit -c pyproject.toml -r src/

# Security: Audit dependencies for known vulnerabilities
check-deps:
	uv export --no-hashes --all-groups -o requirements-ci.txt
	uv run pip-audit -r requirements-ci.txt --no-deps --disable-pip || { \
		exit_code=$$?; \
		$(MAKE) _audit-fail-hint; \
		exit $$exit_code; \
	}

# Internal Helper: Print hint when pip-audit fails
_audit-fail-hint:
	@echo ""
	@echo "======================================================================"
	@echo "             [!] DEPENDENCY VULNERABILITIES DETECTED [!]              "
	@echo "======================================================================"
	@echo "To resolve these vulnerabilities, try the following steps:"
	@echo ""
	@echo "1. DIRECT DEPENDENCY (declared in pyproject.toml):"
	@echo "   Check for a recent patch and update the version in pyproject.toml."
	@echo ""
	@echo "2. TRANSITIVE DEPENDENCY (inside the dependency tree):"
	@echo "   Option A: Find which library is importing the vulnerable package:"
	@echo "      uv tree | grep --color=always -E \"<vuln-lib>|$$\""
	@echo "      (Then try updating the parent library)"
	@echo ""
	@echo "   Option B: Force patch the lockfile directly:"
	@echo "      uv lock --upgrade-package <vuln-lib>"
	@echo "======================================================================"
	@echo ""

# Portal: install, lint, test with coverage and build both deployment profiles
check-portal:
	cd portal && npm ci
	cd portal && npm run lint
	cd portal && npm run format:check
	cd portal && npm audit --audit-level=high
	cd portal && npm run test:coverage
	cd portal && NEXT_PUBLIC_FIREBASE_API_KEY=dummy \
		NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=dummy.firebaseapp.com \
		NEXT_PUBLIC_FIREBASE_PROJECT_ID=dummy \
		NEXT_PUBLIC_FIREBASE_APP_ID=dummy npm run build
	cd portal && bash scripts/prepare-dist.sh out dist-standalone
	cd portal && PORTAL_ASSET_PREFIX=/authorize-static \
		NEXT_PUBLIC_FIREBASE_API_KEY=dummy \
		NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=dummy.firebaseapp.com \
		NEXT_PUBLIC_FIREBASE_PROJECT_ID=dummy \
		NEXT_PUBLIC_FIREBASE_APP_ID=dummy npm run build
	cd portal && bash scripts/prepare-dist.sh out dist-overlay /authorize-static

# Docs: living documentation must not reference the retired external repo
check-docs:
	@if grep -rn "jor-mcp-site" README.md README_pt-br.md CONTRIBUTING.md \
		CONTRIBUTING_pt-br.md docs/README.md docs/README_pt-br.md \
		docs/en/1-technical docs/en/2-replication \
		docs/pt-br/1-tecnico docs/pt-br/2-replicacao; then \
		echo "Living documentation must not reference jor-mcp-site."; \
		exit 1; \
	fi

# Container scan: scan the Docker image for vulnerabilities
check-container:
	docker build -t jor-mcp:latest .
  # TO-DO: Remove '--vuln-type library' once official debian based python docker image is patched in Docker hub
	trivy image --exit-code 1 --severity HIGH,CRITICAL --pkg-types library jor-mcp:latest

# Build and run the Docker container locally
run:
	@echo "Building Docker image..."
	docker build -t jor-mcp:latest .
	@echo "Running Docker container..."
	docker run --rm -p 8080:8080 --env-file .env jor-mcp:latest

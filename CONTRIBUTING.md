<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Contributing to jor-mcp

First off, thank you for considering contributing to `jor-mcp`! It's people like you that make open-source tools for journalism better.

This document provides guidelines and instructions for contributing to this project. 

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Development Standards](#development-standards)
  - [Environment & Dependencies](#environment--dependencies)
  - [Linting & Formatting](#linting--formatting)
  - [Type Checking](#type-checking)
  - [Docstrings & Comments](#docstrings--comments)
  - [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Continuous Integration (CI)](#continuous-integration-ci)
- [Security Scanning](#security-scanning)
- [Reporting Bugs](#reporting-bugs)

---

## Code of Conduct

This project is dedicated to providing a welcoming, diverse, and secure community. Contributors are expected to act with integrity, respect, and professionalism. Let's make open-source tools for journalism better together!

---

## Prerequisites

Before contributing to `jor-mcp`, ensure you have the following installed on your local development machine:

*   **Python:** Version `3.12` or higher is required.
*   **uv:** We use `uv` as our extremely fast Python package and project manager. Follow the [installation instructions here](https://docs.astral.sh/uv/getting-started/installation/).
*   **Docker / Container Runtime:** (Optional but recommended) Useful for running local test instances of dependencies or spinning up the server in a containerized environment. You can use Docker Desktop, Docker community edition, or open-source alternatives like [Colima](https://github.com/abiosoft/colima) or [Podman](https://podman.io/).
*   **Trivy:** Required to run the full local validation suite (`make check` and `make check-container`). Follow the [installation instructions here](https://aquasecurity.github.io/trivy/latest/getting-started/installation/).

---

## Getting Started

To begin contributing to `jor-mcp`:
1.  **Fork and Clone:** Fork the repository on GitHub and clone it locally.
2.  **Environment Setup:** Initialize dependencies using `uv sync` to set up your isolated Python virtual environment.
3.  **Local Checks:** Run `make check` to ensure your local environment passes formatting, linting, typing, and testing.
4.  **Local Run:** Set up your `.env` variables from `.env.example` and execute `make run` to spin up the local service.

---

## Development Standards

### 🌐 Default Language: English

While this project originated in Brazil and supports Portuguese tools, **English is the strict default language for all technical contributions** due to our global funding and audience. 

All information targeted to users and developers must be in English. This explicitly includes:
*   Pull Request descriptions and general communication
*   Commit messages
*   Code comments and variable names
*   Repository documentation (like this file)
*   Technical/Architecture documentation

*(Note: The only exception is the `description` parameter inside `@mcp.tool()` decorators, which currently target Brazilian LLM contexts, as noted in the Docstrings section below).*

This project uses modern Python (>= 3.12) and relies heavily on asynchronous programming. To understand the high-level system design and integration specifics before contributing, please review our **[Technical Documentation](docs/en/1-technical/)**.

To maintain high code quality and consistency, we strictly enforce the following standards. Please ensure your code adheres to these before submitting a Pull Request.

*(Note: AI agents contributing to this project must additionally adhere to the rules defined in `AGENTS.md`)*.

### Environment & Dependencies

We use [`uv`](https://github.com/astral-sh/uv) as our standard dependency manager and environment resolver. **Do not use standard `pip` or `requirements.txt`.**

*   **Install dependencies:** `uv sync`
*   **Add a new dependency:** `uv add <package>`
*   **Run a command in the isolated environment:** `uv run <command>`

### 🛠️ Quick Utilities (Makefile)

To streamline local development, this project provides a `Makefile` with bundled commands:

*   **`make check`**: Runs the entire validation suite in one go. This includes linting (`ruff`), strict formatting checks, static type checking (`mypy`), tests with 90% coverage enforcement, SAST (`bandit`), dependency audit (`pip-audit`), and a container vulnerability scan (`trivy`). **You should run this before opening a Pull Request.**
*   **`make check-sast`**: Runs static application security testing on the source code using `bandit`.
*   **`make check-deps`**: Audits project dependencies for known vulnerabilities using `pip-audit`.
*   **`make check-container`**: Builds the Docker image and scans it for critical vulnerabilities using `trivy`.
*   **`make run`**: Builds the Docker image locally and starts the container on port 8080, reading configuration from your `.env` file.

### Linting & Formatting

We use **Ruff** for all code linting and formatting.

*   **Check code (Lint):** `uv run ruff check .`
*   **Auto-fix safe lint errors:** `uv run ruff check . --fix`
*   **Format code:** `uv run ruff format .`

*Imports must always be absolute (anchored at `src`) and correctly sorted (enforced by Ruff).*

### Type Checking & Data Validation

We employ a dual-strategy for type safety to ensure robust code:

1.  **Static Type Checking (Internal):** All functions, methods, and variables must be fully type-hinted using modern Python 3.12+ syntax (e.g., `list[dict[str, Any]]`, `str | None`). Do not use capitalized imports from the `typing` module like `List`, `Dict`, or `Optional`.
    *   **Run type checker:** `uv run mypy .` *(or `pyright` depending on exact pyproject.toml configuration)*
2.  **Runtime Validation (Boundaries):** We use **Pydantic (v2)** to validate all data entering the system from external sources. Whenever you are parsing external API responses (like WordPress/GitHub JSON), configuration files, or user inputs, you must define and use a Pydantic `BaseModel` to ensure the data matches the expected schema before it enters internal application logic.

### Logging
We rely on OpenTelemetry auto-instrumentation. Do not import or use OpenTelemetry SDKs manually in the application code.
Use the standard Python `logging` module (`logger = logging.getLogger(__name__)`). When logging contextual data, do not use string interpolation; instead, pass variables via the `extra={}` dictionary (e.g., `logger.info("Request successful", extra={"target_url": url})`). This allows OpenTelemetry to index the variables as searchable attributes.

### Docstrings & Comments

*   **Standard:** Use the **Google Docstring Format** for all modules, classes, and complex functions.
*   **MCP Tools:** If you are writing a new Model Context Protocol tool (using the `@mcp.tool()` decorator), the `description` parameter string **must be highly detailed and written in Portuguese**, as the target audience is Brazilian journalism. This is critical for LLM context.
*   **Comments:** Add inline comments sparingly. Focus on explaining *why* complex logic is written a certain way, rather than *what* it does.

### Testing

We use **pytest** (along with `pytest-asyncio` for our async code) to ensure functionality. Every new feature or bug fix should include corresponding tests in the `tests/` directory.

**We enforce a minimum code coverage of 90%.** Pull Requests that drop the coverage below this threshold will not be accepted.

*   **Run all tests:** `uv run pytest`
*   **Run specific test file:** `uv run pytest tests/test_tools.py`
*   **Run tests with coverage:** `uv run pytest --cov=src --cov-fail-under=90`

---

## Submitting Changes

When you are ready to submit a Pull Request, please ensure your contributions align with our versioning automations and documentation standards.

### Documentation Review Requirements

Before any proposed change can be integrated into the `main` branch, you **must** review the `docs/` directory to ensure all relevant documentation is up-to-date with your code changes.

*   **New Features/Tools:** Update the [Technical Reference](docs/en/1-technical/).
*   **Architecture/Logic Changes:** Update the [Technical Reference](docs/en/1-technical/).
*   **New Environment Variables/Dependencies:** Update the [Replication Guides](docs/en/2-replication/).

Pull Requests that introduce changes without corresponding documentation updates will be blocked from merging.

### Branching Strategy & Naming

This repository strictly uses the strategy of **[Trunk-Based Development with Short-Lived Feature Branches](https://trunkbaseddevelopment.com/short-lived-feature-branches/)**. Please ensure your branches are small, focused, and merged frequently.

Branch names must follow the **[Conventional Branch Specification](https://conventional-branch.github.io/)**. 

**For Internal Collaborators (Ambiental Media):**
If you are an internal contributor, you are **required** to include the relevant Issue ID in your branch declaration using the following format:
`<type>/<issue-id>-<short-description>`

*Example:* `feature/0fr4hyt6-wordpress-tool`

### Conventional Commits

We strictly use **[Conventional Commits (v1.0.0)](https://www.conventionalcommits.org/en/v1.0.0/)** for our commit messages. 

We have automations in place that parse merged Pull Requests to automatically bump project versions according to the **[Semantic Versioning 2.0.0 (SemVer)](https://semver.org/)** specification, and to populate GitHub tags and release notes.

**The Rules:**
1. **Minimum Requirement:** At least **one commit** within the scope of your Pull Request must strictly respect the Conventional Commits format (e.g., `feat: add new search parameter`, `fix: resolve JWT validation error`).
2. **Version Bumping (Precedence):** If your Pull Request contains multiple conventional commits, the automated version bump (`MAJOR.MINOR.PATCH`) will be determined by the commit with the **highest precedence**. For example, a `feat` triggers a `MINOR` bump, taking precedence over a `fix` (which triggers a `PATCH` bump). A `BREAKING CHANGE` triggers a `MAJOR` bump and overrides everything else.
3. **Release Notes:** Even though only the highest precedence commit dictates the version number change, **all** information provided by all conventional commits in the Pull Request will be aggregated and used to populate the GitHub release notes.

---

## Continuous Integration (CI)

Every Pull Request automatically triggers the CI pipeline configured in `.github/workflows/ci.yml`. The pipeline is divided into two jobs that must pass before any code can be merged.

### Job: `check`

Runs all code quality and security validations. This job mirrors the local `make check` command, but executes each step individually to prevent any bypass through local Makefile modifications.

| Step | Tool | Behavior |
|---|---|---|
| Lint | `ruff check .` | Reports issues, never auto-fixes |
| Format check | `ruff format --check .` | Reports issues, never auto-fixes |
| Type check | `mypy .` | Fails the job on any type error |
| Tests & Coverage | `pytest --cov=src --cov-fail-under=90` | Fails if coverage drops below 90% |
| SAST | `bandit -c pyproject.toml -r src/` | Fails on medium or higher severity findings |
| Dependency audit | `pip-audit` | Fails on known vulnerabilities |

### Job: `build-and-push`

Only runs if the `check` job completes successfully. Builds the Docker image, scans it for vulnerabilities with Trivy, and pushes it to the Artifact Registry tagged `:pr-<PR_NUMBER>` (e.g. `:pr-44`). This per-PR tag is what the release pipeline later promotes to a versioned tag (see [Release & Versioning](#release--versioning)).

| Step | Detail |
|---|---|
| Build | Docker image built from the project `Dockerfile` |
| Security scan | Trivy scans the image — fails if `CRITICAL` or `HIGH` library vulnerabilities are found |
| Push | Image pushed to Artifact Registry with tag `:pr-<PR_NUMBER>` |

### Job: `commitlint`

Runs in parallel with the other jobs on every Pull Request. It checks that **at least one commit** in the PR range follows the Conventional Commits format. If no commit matches, the job fails and the PR is blocked.

This is the gate that makes automated versioning possible: the release pipeline (below) reads these conventional commits to decide the next version number. See the [Conventional Commits](#conventional-commits) section for the rules.

### Release & Versioning

Versioning is fully automated and lives in a separate workflow, `.github/workflows/release.yml`, which runs **when a Pull Request is merged into `main`** (not on every push). It uses [`python-semantic-release`](https://python-semantic-release.readthedocs.io/) to:

1. Parse the Conventional Commits in the merged PR and compute the next SemVer version (`fix` → PATCH, `feat` → MINOR, `BREAKING CHANGE` → MAJOR).
2. Bump the `version` in `pyproject.toml`, push the `vX.Y.Z` git tag, and publish a GitHub Release with auto-generated notes.
3. Promote the image: the `:pr-<N>` image built during CI is retagged in Artifact Registry to `:vX.Y.Z` and `:latest` — no rebuild, the same digest is promoted.

Deployment itself is **manual**: the `.github/workflows/cd.yml` workflow is triggered on demand (`workflow_dispatch`) with the image tag you want to roll out to Cloud Run. Merging a PR produces a versioned image but does **not** deploy it.

The deployment workflow:
1. Verifies the requested tag actually exists in Artifact Registry (fails fast otherwise).
2. Renders `service.yaml` with `envsubst`, substituting only an explicit allowlist of variables.
3. Deploys the selected image to Cloud Run via `gcloud run services replace`.

Because deployment consumes an existing image by tag, it is fully decoupled from versioning: you choose exactly which build reaches production, and the deploy step never changes the project version.

### Required GitHub Secrets

For the `build-and-push` job to authenticate with Google Cloud, the following secret must be configured in the repository settings by a maintainer:

| Secret | Description |
|---|---|
| `GCP_SA_KEY` | JSON key of a GCP Service Account with `roles/artifactregistry.writer` permission |

### Interpreting CI Failures

*   **Lint/Format failure:** Run `uv run ruff check .` and `uv run ruff format --check .` locally to see the reported issues.
*   **Type check failure:** Run `uv run mypy .` locally and fix all reported type errors.
*   **Test/Coverage failure:** Run `uv run pytest --cov=src --cov-fail-under=90` locally. Ensure new code has corresponding tests.
*   **SAST/Dependency failure:** Run `make check-sast` or `make check-deps` locally to inspect the findings.
*   **Container scan failure:** A critical vulnerability was found in the Docker image. Review the Trivy report in the CI logs and update the affected dependency or base image.

---

## Security Scanning

This project integrates three open-source security scanning tools to mitigate vulnerabilities before any code is published. All three tools run automatically in the CI pipeline, and two of them (`bandit` and `pip-audit`) can be run locally via the `Makefile`.

### Tools

*   **Bandit** — Static Application Security Testing (SAST). Analyzes the Python source code in `src/` for common security issues such as hardcoded credentials, unsafe function calls, and injection risks.

*   **pip-audit** — Software Composition Analysis (SCA). Audits all project dependencies (including dev dependencies) against known vulnerability databases (PyPA Advisory Database and OSV) to detect packages with published CVEs.

*   **Trivy** — Container vulnerability scanner. Scans the built Docker image for critical vulnerabilities in OS packages and application dependencies. Trivy runs in the CI pipeline via a GitHub Action and **must also be installed locally** to run `make check` and `make check-container` on your machine.

### Running Locally
```bash
# SAST only
make check-sast

# Dependency audit only
make check-deps

# Container scan only (requires Docker and Trivy installed locally)
make check-container

# Full suite including all security scans
make check
```

### Installing Trivy Locally

Trivy is the only security tool that requires a separate local installation (Bandit and pip-audit are installed automatically via `uv sync`). Follow the official [Trivy installation guide](https://aquasecurity.github.io/trivy/latest/getting-started/installation/) for your operating system.

### Severity Policy

The CI pipeline fails the build on:
- **Trivy:** `CRITICAL` and `HIGH` library vulnerabilities (`--severity CRITICAL,HIGH`).
- **Bandit:** `MEDIUM` and `HIGH` severity findings. Bandit's severity scale is `LOW`/`MEDIUM`/`HIGH` (there is no "critical" level), and the `-ll` flag in `ci.yml` sets the threshold to medium-and-above.

Findings below these thresholds are reported in the logs for awareness but do not block the pipeline. These thresholds can be adjusted in the `ci.yml` workflow file and in `pyproject.toml` (`[tool.bandit]`).

---

## Reporting Bugs

Please report any bugs, security vulnerabilities, or issue findings by opening an issue on GitHub. Include:
*   A clear, descriptive title.
*   Steps to reproduce the issue.
*   The expected vs actual behavior.
*   Relevant logs, terminal outputs, or screenshot references.

---

## Documentation Formatting Guidelines

This section defines the strict rules that all human and AI contributors must follow when creating or modifying markdown files in the `jor-mcp` repository.

### 1. File Naming and Structure
*   **Kebab-case only:** All markdown files must be named using lowercase letters and hyphens (e.g., `api-contracts.md`).
*   **Bilingual parity:** All files in `docs/en/` must have a corresponding translation in `docs/pt-br/`.
*   **No spaces in paths:** Directory names must follow `kebab-case`.

### 2. Markdown Formatting
*   **Headings:** Start every file with a single `# Heading 1` (Title). Use `##` and `###` for subsequent sections.
*   **Lists:** Always use hyphens (`-`) for unordered lists.
*   **Code Blocks:** Always specify the language (e.g., `python`, `bash`, `json`, `http`). Use `mermaid` for all diagrams.
*   **Diagrams:** Use Mermaid.js. Include `%%{init: {'theme': 'dark'}}%%` at the top.

### 3. Language & Tone
*   **Tone:** Professional, concise, and direct.
*   **English First:** English is the source of truth for technical documentation. Technical terms (e.g., "Rate Limiting", "Middleware") must remain in English in both EN and PT-BR versions.
*   **Voice:** Active voice preferred.

### 4. Cross-Referencing
*   **Relative Links:** Use only relative links (e.g., `[See Architecture](../1-technical/architecture.md)`). Never use absolute GitHub URLs.

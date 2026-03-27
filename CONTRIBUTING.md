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
- [Reporting Bugs](#reporting-bugs)

---

## Code of Conduct
*(Placeholder: Briefly describe the expected behavior of contributors or link to a CODE_OF_CONDUCT.md file.)*

---

## Prerequisites

Before contributing to `jor-mcp`, ensure you have the following installed on your local development machine:

*   **Python:** Version `3.12` or higher is required.
*   **uv:** We use `uv` as our extremely fast Python package and project manager. Follow the [installation instructions here](https://docs.astral.sh/uv/getting-started/installation/).
*   **Docker / Container Runtime:** (Optional but recommended) Useful for running local test instances of dependencies or spinning up the server in a containerized environment. You can use Docker Desktop, Docker community edition, or open-source alternatives like [Colima](https://github.com/abiosoft/colima) or [Podman](https://podman.io/).

---

## Getting Started
*(Placeholder: Step-by-step instructions on how to fork the repo, clone it, and set up environment variables.)*

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

This project uses modern Python (>= 3.12) and relies heavily on asynchronous programming. To understand the high-level system design and integration specifics before contributing, please review our **[Technical Documentation](docs/1-technical/)**.

To maintain high code quality and consistency, we strictly enforce the following standards. Please ensure your code adheres to these before submitting a Pull Request.

*(Note: AI agents contributing to this project must additionally adhere to the rules defined in `AGENTS.md`)*.

### Environment & Dependencies

We use [`uv`](https://github.com/astral-sh/uv) as our standard dependency manager and environment resolver. **Do not use standard `pip` or `requirements.txt`.**

*   **Install dependencies:** `uv sync`
*   **Add a new dependency:** `uv add <package>`
*   **Run a command in the isolated environment:** `uv run <command>`

### 🛠️ Quick Utilities (Makefile)

To streamline local development, this project provides a `Makefile` with bundled commands:

*   **`make check`**: Runs the entire validation suite in one go. This includes linting (`ruff`), strict formatting checks, static type checking (`mypy`), and running all tests while enforcing the 90% coverage rule. **You should run this before opening a Pull Request.**
*   **`make run`**: Builds the Docker image locally and starts the container on port 8080, reading configuration from your `.env` file.

### Linting & Formatting

We use **Ruff** for all code linting and formatting.

*   **Check code (Lint):** `uv run ruff check .`
*   **Auto-fix safe lint errors:** `uv run ruff check . --fix`
*   **Format code:** `uv run ruff format .`

*Imports must always be absolute (anchored at `src`) and correctly sorted (enforced by Ruff).*

### Type Checking

All functions, methods, and variables must be fully type-hinted using modern Python 3.12+ syntax (e.g., `list[dict[str, Any]]`, `str | None`). Do not use capitalized imports from the `typing` module like `List`, `Dict`, or `Optional`.

We enforce strict static type checking.

*   **Run type checker:** `uv run mypy .` *(or `pyright` depending on exact pyproject.toml configuration)*

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

*   **New Features/Tools:** Update the [Usage Guides](docs/3-usage/).
*   **Architecture/Logic Changes:** Update the [Technical Documentation](docs/1-technical/).
*   **New Environment Variables/Dependencies:** Update the [Deployment Guides](docs/2-deployment/).

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

## Reporting Bugs
*(Placeholder: Instructions on how to submit issue tickets, what information to include, logs, etc.)*

## Issue ticket number and link
<!-- Please provide the Issue ticket number (e.g., Fixes #123) and a link to the original issue, if applicable. -->


## Describe your changes
<!-- Please provide a clear and concise description of what this PR changes, fixes, or adds. -->


## 🚨 Contributor Checklist
<!-- 
💡 TIP: If you are still working through this checklist, please open this Pull Request as a **Draft**. 
Once all boxes below are checked and you are ready for a code review, you can mark the PR as "Ready for review". 
-->

- [ ] **Language:** All technical communication in this PR (description, commits, code comments) is in English.
- [ ] **Conventional Commits:** At least one commit in this PR follows the [Conventional Commits v1.0.0](https://www.conventionalcommits.org/) format to trigger automated Semantic Versioning.
- [ ] **Code Coverage:** I have written/updated tests for my changes, and the project maintains the **90% test coverage minimum** (`uv run pytest --cov=src --cov-fail-under=90`).
- [ ] **Documentation Sync:** I have reviewed the `docs/` directory and updated all relevant Technical, Deployment, or Usage documentation to reflect my changes.
- [ ] **Linting & Formatting:** My code passes all `ruff` checks and formatting rules (`uv run ruff check .` and `uv run ruff format .`).
- [ ] **Type Checking:** My code is strictly typed and passes `mypy` checks (`uv run mypy .`).

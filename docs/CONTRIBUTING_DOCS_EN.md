# Documentation Formatting Guidelines

This document defines the strict rules that all human and AI contributors must follow when creating or modifying markdown files in the `jor-mcp` repository.

## 1. File Naming and Structure
- **Kebab-case only:** All markdown files must be named using lowercase letters and hyphens (e.g., `api-contracts.md`).
- **Bilingual parity:** All files in `docs/en/` must have a corresponding translation in `docs/pt-br/`.
- **No spaces in paths:** Directory names must follow `kebab-case`.

## 2. Markdown Formatting
- **Headings:** Start every file with a single `# Heading 1` (Title). Use `##` and `###` for subsequent sections.
- **Lists:** Always use hyphens (`-`) for unordered lists.
- **Code Blocks:** Always specify the language (e.g., `python`, `bash`, `json`, `http`). Use `mermaid` for all diagrams.
- **Diagrams:** Use Mermaid.js. Include `%%{init: {'theme': 'dark'}}%%` at the top.

## 3. Language & Tone
- **Tone:** Professional, concise, and direct.
- **English First:** English is the source of truth. Technical terms (e.g., "Rate Limiting", "Middleware") must remain in English in both EN and PT-BR versions.
- **Voice:** Active voice preferred.

## 4. Cross-Referencing
- **Relative Links:** Use only relative links (e.g., `[See Architecture](../1-technical/architecture.md)`). Never use absolute GitHub URLs.

<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right vertical-align:middle" height="50em">

---

<p align="center" height="120em"><img src="assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left vertical-align:middle" height="180em"></p>

---

[Read in English](README.md) | [Leia em Português](README_pt-br.md)

---

## Status

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE) [![Docker Ready](https://img.shields.io/badge/docker-ready-blue.svg)](#installation-via-docker)[![codecov](https://codecov.io/github/ambiental-media/jor-mcp/graph/badge.svg?token=AHANHTFVR5)](https://codecov.io/github/ambiental-media/jor-mcp)

### ⚠️ Project Status: Beta

The current release state of `jor-mcp` is **Beta**.
*   **Characteristics:**
    *   Limited and selective invitations.
    *   Requires registration and prior user approval.
    *   Often involves an NDA (Non-Disclosure Agreement) in commercial projects.
*   **Objective:**
    *   Validate user experience (UX) with real people.
    *   Test server load with a controlled number of concurrent users.
    *   Detect issues specific to regional context or configurations.
*   **Advantages over Alpha:** Greater diversity of test profiles without risk to the public brand.

### 🚀 Join our Replication Pilot!

We are gearing up to test the **replicability** of `jor-mcp` by deploying and adapting it in the infrastructure of a **partner journalism organization**. 
*   **The Pilot Round:** We will select **one pilot partner** first to receive hands-on setup support.
*   **The Goal:** This round will be used to refine our setup guides, resulting in a comprehensive **Replication Playbook** along with standard **Infrastructure as Code (IaC)** and **Configuration as Code (CaC)** templates to make future self-service deployments extremely seamless.
*   **Want to participate?** If your newsroom wants to pilot secure AI search over WordPress and GitHub, please **reach out to us** to express interest!

---

## About

`jor-mcp` is an open-source [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server specifically designed for journalism organizations. 

Originally developed by [Ambiental Media](https://ambiental.media/) with support from global journalism initiatives, this server bridges the gap between Large Language Models (LLMs) and standard newsroom infrastructure, allowing AI agents to securely search, retrieve, and analyze content across your organization's WordPress instances and internal GitHub repositories.

By deploying your own instance of `jor-mcp`, your newsroom can empower AI workflows to fact-check against your own archives, summarize internal reports, and seamlessly access proprietary data context.

## Features

*   **WordPress Integration:** Search published articles, retrieve full content, and analyze metadata directly from your newsroom's CMS.
*   **GitHub Integration:** Query internal repositories, research data, and codebases associated with your journalistic investigations.
*   **Secure Access:** Token-based authentication (JWT) ensures only authorized AI agents or internal systems can access your data.
*   **Containerized:** Easy to deploy anywhere using Docker.
*   **Easily Forkable:** Designed to be easily cloned, configured via environment variables, and deployed on standard cloud infrastructure.

## Documentation

Comprehensive documentation for all audiences is available in the [`docs/`](docs/) directory:
*   [Technical Architecture](docs/en/1-technical/)
*   [Replication Guides](docs/en/2-replication/)
*   [History and Specifications](docs/en/3-history-and-specs/)
*   [Legal Framework](docs/en/4-legal/)

## Getting Started

### Prerequisites

To run your own instance of `jor-mcp`, you only need a container runtime:
*   [Docker](https://www.docker.com/) (or open-source alternatives like [Colima](https://github.com/abiosoft/colima) or [Podman](https://podman.io/)).

### Installation via Docker (Recommended)

The easiest way to get `jor-mcp` running is via Docker.

1.  **Pull the image:**
    *(Placeholder: `docker pull ghcr.io/ambiental-media/jor-mcp:latest` - Assuming GitHub Container Registry will be used)*

2.  **Configure Environment Variables:**
    Create a `.env` file to configure your newsroom's specific access points:
    ```env
    WORDPRESS_API_URL=https://yoursite.com/wp-json/wp/v2
    MCP_GITHUB_TOKEN=your_github_personal_access_token
    JWT_SECRET=your_secure_random_string_for_auth
    PORT=8080
    ```

3.  **Build and Run the container:**
    You can build and start the server instantly using the provided Makefile:
    ```bash
    make run
    ```
    *(Alternatively, run `docker build -t jor-mcp:latest .` followed by `docker run --rm -p 8080:8080 --env-file .env jor-mcp:latest`)*

## Configuration for Your Newsroom

To adapt `jor-mcp` for your specific organization, you only need to update the environment variables in your `.env` file. The core logic is designed to be agnostic and will dynamically query the WordPress and GitHub endpoints you provide.

For detailed configuration options (like setting up the `.env` file for your specific newsroom) and deployment guides for various cloud providers, please refer to our **[Replication Guides](docs/en/2-replication/)**.

## Advanced: Installation from Source (For Developers)

If you wish to modify the code or run the server outside of a container, you will need to install it from source.

1.  **Prerequisites:** Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).
2.  **Clone the repository:** `git clone https://github.com/ambiental-media/jor-mcp.git`
3.  **Install dependencies:** `uv sync`
4.  **Run the server:** `uv run uvicorn src.server:app --host 0.0.0.0 --port 8080`

## Using the MCP Server

Once deployed, you can connect your preferred LLM interface (e.g., Claude Desktop, custom AI agents) to your `jor-mcp` instance using the standard Model Context Protocol.

For instructions on connecting Claude Desktop or other AI agents, and a reference of available tools, see our **[Technical Documentation](docs/en/1-technical/)**.

## Contributing

We welcome contributions from other journalism organizations and the open-source community! 

Please read our [Contributing Guidelines](docs/CONTRIBUTING_DOCS_EN.md) to learn about our development standards, environment setup, and code quality requirements before submitting a Pull Request.

AI Agents assisting with this repository must adhere to the rules in [AGENTS.md](AGENTS.md).

## Acknowledgements & Funding

The development of `jor-mcp` was made possible through the generous support of two major journalism initiatives:

*   **[JournalismAI Innovation Challenge](https://www.journalismai.info/programmes/innovation):** Supported via "JournalismAI" (a project of POLIS Journalism at LSE) and the "Google News Initiative," targeting the global journalism ecosystem.
*   **[Codesinfo](https://codesinfo.com.br/en/home-english/):** Supported via "Projor" and the "Google News Initiative," targeting the Brazilian journalism ecosystem.

## Roadmap

*   [🚀 Roadmap](docs/en/3-history-and-specs/roadmap.md)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

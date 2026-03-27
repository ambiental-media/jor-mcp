# Jor-MCP

[![License: TBD](https://img.shields.io/badge/License-TBD-lightgrey.svg)](#license)
[![Docker Ready](https://img.shields.io/badge/docker-ready-blue.svg)](#installation-via-docker)

`jor-mcp` is an open-source [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server specifically designed for journalism organizations. 

Originally developed by [Ambiental Media](https://ambiental.media/) with support from global journalism initiatives, this server bridges the gap between Large Language Models (LLMs) and standard newsroom infrastructure, allowing AI agents to securely search, retrieve, and analyze content across your organization's WordPress instances and internal GitHub repositories.

By deploying your own instance of `jor-mcp`, your newsroom can empower AI workflows to fact-check against your own archives, summarize internal reports, and seamlessly access proprietary data context.

## Features

*   **WordPress Integration:** Search published articles, retrieve full content, and analyze metadata directly from your newsroom's CMS.
*   **GitHub Integration:** Query internal repositories, research data, and codebases associated with your journalistic investigations.
*   **Secure Access:** Token-based authentication (JWT) ensures only authorized AI agents or internal systems can access your data.
*   **Containerized:** Easy to deploy anywhere using Docker.
*   **Easily Forkable:** Designed to be easily cloned, configured via environment variables, and deployed on standard cloud infrastructure.

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
    GITHUB_TOKEN=your_github_personal_access_token
    JWT_SECRET=your_secure_random_string_for_auth
    PORT=8080
    ```

3.  **Run the container:**
    ```bash
    docker run -d -p 8080:8080 --env-file .env jor-mcp:latest
    ```

## Configuration for Your Newsroom

To adapt `jor-mcp` for your specific organization, you only need to update the environment variables in your `.env` file. The core logic is designed to be agnostic and will dynamically query the WordPress and GitHub endpoints you provide.

*(Placeholder: Provide any additional details here if specific WordPress plugins or GitHub organizational settings are required).*

## Advanced: Installation from Source (For Developers)

If you wish to modify the code or run the server outside of a container, you will need to install it from source.

1.  **Prerequisites:** Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).
2.  **Clone the repository:** `git clone https://github.com/ambiental-media/jor-mcp.git`
3.  **Install dependencies:** `uv sync`
4.  **Run the server:** `uv run uvicorn src.server:app --host 0.0.0.0 --port 8080`

## Using the MCP Server

Once deployed, you can connect your preferred LLM interface (e.g., Claude Desktop, custom AI agents) to your `jor-mcp` instance using the standard Model Context Protocol.

*(Placeholder: Provide a brief example of the JSON configuration required by clients to connect to this server, including how to pass the JWT token).*

## Contributing

We welcome contributions from other journalism organizations and the open-source community! 

Please read our [Contributing Guidelines](CONTRIBUTING.md) to learn about our development standards, environment setup, and code quality requirements before submitting a Pull Request.

AI Agents assisting with this repository must adhere to the rules in [AGENTS.md](AGENTS.md).

## Acknowledgements & Funding

The development of `jor-mcp` was made possible through the generous support of two major journalism initiatives:

*   **[Codesinfo](https://codesinfo.com.br/):** Supported via "Projor" and the "Google News Initiative," targeting the Brazilian journalism ecosystem.
*   **Journalism AI Innovation Challenge:** Supported via "JournalismAI" with "POLIS Journalism at LSE" and the "Google News Initiative," targeting the global journalism market.

## License

*(Placeholder: The open-source license for this project has not yet been determined. Please check back later for licensing details.)*

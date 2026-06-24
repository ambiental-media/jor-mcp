# Architecture Overview

*(Placeholder: High-level system design, FastMCP, async I/O strategy, dependency injection).*

### Data Validation Layer
All external data ingress (API responses from WordPress/GitHub, environment variables, client requests) must pass through a **Pydantic v2** validation layer. This ensures that the core application logic, which is statically checked by Mypy, only ever operates on guaranteed, type-safe structures.

### Telemetry & Observability
The application relies strictly on **OpenTelemetry Auto-Instrumentation**. Traces, metrics, and logs are automatically collected from the ASGI layer (FastMCP/Starlette), HTTP clients (`httpx`), and standard Python `logging`. 
- **No Manual Tracing:** Developers should avoid importing `opentelemetry` SDK components into business logic. 
- **Logging:** Use the standard Python `logging` module. All logs are automatically intercepted, enriched with trace contexts, and exported via OTLP to the configured observability backend.
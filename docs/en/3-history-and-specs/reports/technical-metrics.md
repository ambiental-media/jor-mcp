<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Technical Metrics

Post-launch operational report for the Jor-MCP server, built exclusively from telemetry that already existed at snapshot time. No instrumentation, configuration, or synthetic traffic was added to produce this report.

| Field | Value |
|---|---|
| Snapshot date | 2026-10-25 |
| Measurement window | 2026-09-25T20:28:36Z → 2026-10-25 (30 days, full log retention) |
| Data extraction | 2026-10-25T20:55Z (counts drift slightly with live traffic) |
| Service | `jor-mcp-server` |
| Revision | `jor-mcp-server-00018-dxn` (image `v0.13.1`) |
| GCP project | `jor-mcp`, region `us-central1` |
| Runtime | Cloud Run, 1 vCPU / 1 GiB, concurrency 80, timeout 300 s, min instances 0, max instances 5 |

## 1. Executive Summary

| # | Indicator | Target | Measured | Verdict |
|---|---|---|---|---|
| 1 | Response time | Mean < 10 s | Mean **0.73 s**, p95 **0.64 s**, p99 **2.52 s**; 2 requests at 301 s | **Pass** on mean; cold start at risk |
| 2 | Availability | ≥ 95% | Infra **99.64%**, legit traffic **98.30%**; 2 days below 95% | **Pass** over 30 days; **fail** on 2 individual days |
| 3 | AI assistant integration | ≥ 2 assistants | Claude (580 MCP calls) + ChatGPT (4 MCP calls, 18 OAuth token calls); Gemini absent | **Pass** |
| 4 | Query precision | ≥ 90% relevant | 35.7% of searches returned zero results; no relevance labels | **Not demonstrated** |
| 5 | Real-time updates | No reindexing | No cache, no index; live probe showed 0 staleness | **Pass** by design; single-point evidence |

## 2. Data Sources and Method

All data is stored telemetry, read with read-only scopes through the `mcp-viewer@jor-mcp.iam.gserviceaccount.com` impersonation.

| Source | Contents used |
|---|---|
| Cloud Monitoring | `run.googleapis.com/request_count`, `request_latencies`, `container/startup_latencies`, `container/cpu/utilizations`, `container/memory/utilizations`, `container/instance_count` |
| Cloud Logging `run.googleapis.com/requests` | Status, latency, URL, method, user agent, trace ID per request |
| Cloud Logging `run.googleapis.com/stdout` | Structured JSON application logs: search queries, result counts, authentication events, tool errors |
| Cloud Run revision spec | Deployed environment, scaling, timeouts |

### 2.1 Service Level Indicators

- **Infra availability** = `1 − (5xx / all requests)`. Includes internet scanner noise.
- **Legit-traffic availability** = `1 − (5xx / requests to /mcp* and /api/oauth*)`. Excludes scanner paths (`/`, `/.env`, `/wp-*`, `/ws`, `/socket.io`, `/raw`) that never reach the MCP application.
- **Response time** = latency of `POST /mcp` with status `200`/`202`, read from request logs.
- **Excluded from response time:** `GET /mcp` SSE sessions. These are long-lived streams held open until the 300 s timeout (observed p95 301 s; 33.6% of sessions reach the deadline), so their duration measures session lifetime, not query latency.

### 2.2 Instrumentation State at Snapshot

- Application tracing exists but was not exported: `OTEL_EXPORTER_OTLP_ENDPOINT` is set to `http://localhost:4318` and `OTEL_TRACES_EXPORTER` is unset, so the exporter resolves to `none`. No spans reach Cloud Trace.
- No Cloud Monitoring dashboards, uptime checks, alert policies, or log-based metrics existed.
- Application logs carry `trace_id`/`span_id`, so request logs and application logs correlate (see Section 8).

## 3. Response Time (Indicator 1)

Source: 1,158 successful `POST /mcp` requests (status 200/202), 30-day window.

| Metric | Value |
|---|---|
| Requests | 1,158 |
| Mean | **0.73 s** |
| p50 | 0.14 s |
| p90 | 0.37 s |
| p95 | 0.64 s |
| p99 | 2.52 s |
| Max | 301.00 s |
| Requests > 10 s | 2 (0.17%) |
| Within target | **99.83%** |

### 3.1 By Client

| Client (user agent family) | Calls | Mean | p95 | First seen | Last seen |
|---|---|---|---|---|---|
| `Claude-User` | 580 | 1.27 s | 0.56 s | 2026-09-25 | 2026-10-24 |
| `codex-mcp-client` | 377 | 0.17 s | 0.74 s | 2026-10-20 | 2026-10-20 |
| `opencode` | 180 | 0.20 s | 0.46 s | 2026-10-01 | 2026-10-25 |
| `(none)` | 11 | 0.52 s | 2.58 s | 2026-10-21 | 2026-10-21 |
| `undici` | 6 | 0.13 s | 0.21 s | 2026-10-21 | 2026-10-21 |
| `openai-mcp` | 4 | 0.81 s | 2.76 s | 2026-10-20 | 2026-10-20 |

### 3.2 Cold Start Caveat

Minimum instances is `0`, so the first request after an idle period waits for container startup. `run.googleapis.com/container/startup_latencies` p95 = **24.03 s** over the window. This time is not part of Cloud Run request latency but is part of the user-perceived wait, so a cold request can exceed the 10 s target even when the reported mean is 0.73 s.

**Verdict:** target met on average. Two POST outliers hit 301 s and cold start p95 is 24.03 s; both must be disclosed alongside the average.

## 4. Availability (Indicator 2)

Source: 25,408 request log entries over 30 days.

| SLI | Numerator | Denominator | Result |
|---|---|---|---|
| Infra availability | 25,317 non-5xx | 25,408 | **99.64%** |
| Legit-traffic availability | 4,101 non-5xx | 4,172 legit requests | **98.30%** |

Status distribution (30 days):

| Status | Count | Share |
|---|---|---|
| 401 | 22,262 | 87.6% |
| 200 | 2,033 | 8.0% |
| 404 | 416 | 1.6% |
| 202 | 261 | 1.0% |
| 400 | 247 | 1.0% |
| 502 | 71 | 0.28% |
| 429 | 68 | 0.27% |
| 201 | 26 | 0.10% |
| 500 | 20 | 0.08% |
| 409 | 4 | 0.02% |

The 401 majority is internet scanning: requests for `/.env`, `/wp-login.php`, `/socket.io/`, root paths, and crawler user agents such as `libredtail-http`, `l9explore`, `zgrab`, and `WP-Safe-Scanner`. Most of them target paths outside the MCP application; roughly 2,000 of them (9%) hit `/mcp` and were rejected by `AuthMiddleware` before any tool executed. Because these probes dominate the denominator, the raw 2xx ratio (8.0%) is not a usable availability measure. On `/mcp` itself, ≈1,980 of 3,155 POST attempts (63%) were rejected with 401, which points to expired or missing access tokens rather than server failure.

### 4.1 5xx Breakdown

| Status | Path | Count | Cause |
|---|---|---|---|
| 502 | `/api/oauth/token` | 54 | OAuth token proxy upstream failure, concentrated 2026-10-12 → 2026-10-16 |
| 502 | `/api/oauth/approve` | 17 | OAuth consent proxy upstream failure, same period |
| 500 | `/ws`, `/socket.io/`, `/raw`, `/` | 20 | Scanner traffic hitting unsupported routes |

No 5xx was recorded on `/mcp` itself.

### 4.2 Daily Series

| Date | Requests | 5xx | Infra availability | Legit availability |
|---|---|---|---|---|
| 2026-09-25 | 49 | 0 | 100.00% | 100.00% |
| 2026-09-26 | 498 | 0 | 100.00% | 100.00% |
| 2026-09-27 | 1,074 | 4 | 99.63% | 100.00% |
| 2026-09-28 | 734 | 0 | 100.00% | 100.00% |
| 2026-09-29 | 431 | 0 | 100.00% | 100.00% |
| 2026-09-30 | 692 | 0 | 100.00% | 100.00% |
| 2026-10-01 | 285 | 0 | 100.00% | 100.00% |
| 2026-10-02 | 828 | 0 | 100.00% | 100.00% |
| 2026-10-03 | 721 | 0 | 100.00% | 100.00% |
| 2026-10-04 | 395 | 0 | 100.00% | 100.00% |
| 2026-10-05 | 1,239 | 0 | 100.00% | 100.00% |
| 2026-10-06 | 285 | 4 | 98.60% | 100.00% |
| 2026-10-07 | 1,298 | 0 | 100.00% | 100.00% |
| 2026-10-08 | 949 | 0 | 100.00% | 100.00% |
| 2026-10-09 | 468 | 0 | 100.00% | 100.00% |
| 2026-10-10 | 625 | 0 | 100.00% | 100.00% |
| 2026-10-11 | 1,036 | 0 | 100.00% | 100.00% |
| 2026-10-12 | 476 | 4 | 99.16% | 95.65% |
| 2026-10-13 | 1,767 | 19 | 98.92% | 97.47% |
| 2026-10-14 | 1,316 | 36 | 97.26% | **94.04%** |
| 2026-10-15 | 1,862 | 8 | 99.57% | 97.52% |
| 2026-10-16 | 739 | 6 | 99.19% | **72.73%** |
| 2026-10-17 | 522 | 0 | 100.00% | 100.00% |
| 2026-10-18 | 316 | 0 | 100.00% | 100.00% |
| 2026-10-19 | 1,308 | 2 | 99.85% | 95.00% |
| 2026-10-20 | 1,734 | 0 | 100.00% | 100.00% |
| 2026-10-21 | 1,434 | 0 | 100.00% | 100.00% |
| 2026-10-22 | 1,005 | 0 | 100.00% | 100.00% |
| 2026-10-23 | 239 | 4 | 98.33% | 100.00% |
| 2026-10-24 | 454 | 0 | 100.00% | 100.00% |
| 2026-10-25 | 629 | 4 | 99.36% | 100.00% |

Two days fall below the 95% target: 2026-10-14 (94.04%) and 2026-10-16 (72.73%). The 2026-10-16 value comes from a small denominator (22 legit requests, 6 failures), so a handful of failed OAuth calls moves the daily rate sharply.

**Verdict:** the 30-day aggregate meets the target on both definitions. The daily series does not, driven entirely by the OAuth proxy, not by the MCP endpoint.

## 5. AI Assistant Integration (Indicator 3)

Source: user agents on successful `POST /mcp` requests, cross-checked against application authentication logs.

| Assistant / client | Family | Calls | Evidence |
|---|---|---|---|
| Claude Desktop | `Claude-User` | 580 | Active 2026-09-25 → 2026-10-24 |
| ChatGPT connector | `openai-mcp` (MCP), `openai-connectors-oauth` (OAuth) | 4 + 18 | First seen 2026-10-20, still active 2026-10-25 |
| OpenAI Codex CLI | `codex-mcp-client` | 377 | Single-day run, 2026-10-20 |
| OpenCode | `opencode` | 180 | 2026-10-01 → 2026-10-25 |
| Gemini | — | 0 | **No request in the window** |

Authentication evidence: 1,493 `Authenticated request` events in application logs at extraction, including tier metadata (`tier: pro`) issued by the OAuth flow.

**Verdict:** the two-assistant target is met (Claude and ChatGPT). Gemini integration is unproven in the data.

## 6. Query Effectiveness (Indicator 4)

Only Tier A measurement was authorized: statistics derived from already-logged queries, without replaying queries or judging relevance. This section therefore reports proxies, not precision.

Source: 28 logged searches, 23 distinct queries.

| Metric | WordPress | GitHub |
|---|---|---|
| Searches | 28 | 28 |
| Mean results | 2.29 | **0.00** |
| Median results | 1 | 0 |
| Max results | 7 | 0 |
| Zero-result searches | 10 (35.7%) | 28 (100%) |
| Upstream failures | 0 | 0 |
| Malformed results skipped | 0 | 0 |

Related activity: 18 `WordPress article fetched` events, 0 article-fetch errors, and 10 `Error calling tool 'search_content'` events. The tool raises `ToolError` exactly when the merged result set is empty, so those 10 errors correspond to the 10 zero-result searches.

Zero-result queries observed:

- `Formoso do Rio Preto`
- `Operação Faroeste`
- `Cerrado Amazon water cycle rivers water`
- `rios voadores`
- `Cerrado Amazônia rios voadores`
- `Cerrado Amazônia bacias hidrográficas rios voadores`
- `Cerrado Amazônia chuvas rios voadores`
- `Jor-MCP` (repeated)

Two findings constrain any precision claim:

1. **The GitHub source returned zero results in every observed search.** Either the i18n corpus does not contain the queried terms or the in-memory matcher is not reaching it. With 28 of 28 empty, this source contributes nothing to search effectiveness.
2. **More than a third of searches end with no answer at all.** A zero-result response is not a wrong answer, but from the user's intent perspective it is still a failed query.

**Verdict:** the 90% precision target cannot be asserted from existing telemetry. No relevance labels, result identifiers, or user feedback exist in the logs, and the search path is keyword-based (WordPress `search` parameter plus substring matching over GitHub JSON), not semantic.

## 7. Real-time Updates (Indicator 5)

Freshness is an architectural property here, not a pipeline: there is no index and no cache layer.

- `src/services/wordpress.py` fetches every article directly from the WordPress REST API (`_fetch_post_by_id`, `_fetch_post_by_slug`, `fetch_latest_posts`).
- `src/services/github.py` reads repository files on each call (`_fetch_repo_files`, `fetch_github_i18n_content`).
- `pyproject.toml` declares no caching dependency, and the shared `httpx.AsyncClient` in `src/http_client.py` configures pooling and timeouts only.

Live probe on 2026-10-25:

| Check | Result |
|---|---|
| WordPress latest post | id `4229`, published `2026-10-14T16:10:04`, modified `2026-10-15T17:33:47` |
| WordPress REST API at probe time | Same `id`, `date`, and `modified` values |
| Jor-MCP data path | Calls the same REST endpoint on every request |

Measured staleness at probe time: **0**. Editorial changes become visible on the next query; there is no reindex step to wait for.

**Verdict:** target met by design. The evidence is a single-point probe plus code inspection, because no historical freshness series exists in the stored telemetry.

## 8. Evidence

All commands were run read-only against project `jor-mcp`, using impersonation of `mcp-viewer@jor-mcp.iam.gserviceaccount.com`. IP addresses and user identifiers are redacted.

### 8.1 Request Volume and Status

```bash
gcloud logging read \
  'logName="projects/jor-mcp/logs/run.googleapis.com%2Frequests"
   AND timestamp>="2026-09-25T00:00:00Z"' \
  --limit=100000 --format=json
```

Sample request log entry, sanitized:

```json
{
  "httpRequest": {
    "latency": "0.131298442s",
    "requestMethod": "POST",
    "requestUrl": "https://jormcp.ambiental.media/mcp?codemode=false",
    "status": 200,
    "userAgent": "opencode/latest/2.1.2/cli"
  },
  "resource": {
    "type": "cloud_run_revision",
    "labels": {
      "service_name": "jor-mcp-server",
      "revision_name": "jor-mcp-server-00018-dxn"
    }
  },
  "timestamp": "2026-10-25T19:40:44.725319Z",
  "trace": "projects/jor-mcp/traces/46e1ade1a6b3e5af783cec2a96dfe671"
}
```

Response time slice:

```bash
gcloud logging read \
  'logName="projects/jor-mcp/logs/run.googleapis.com%2Frequests"
   AND httpRequest.requestMethod="POST"
   AND httpRequest.requestUrl:"/mcp"
   AND (httpRequest.status=200 OR httpRequest.status=202)' \
  --limit=100000 --format=json
```

### 8.2 Trace Correlation

Two application log entries sharing the trace above, sanitized (`uid` replaced):

```json
{"timestamp": "2026-10-25T19:40:44.733335Z",
 "jsonPayload": {"logger": "src.middleware.auth",
                 "message": "Authenticated request",
                 "extra": {"tier": "pro", "uid": "<redacted>"}}}
{"timestamp": "2026-10-25T19:40:44.857615Z",
 "jsonPayload": {"logger": "uvicorn.access",
                 "message": "POST /mcp?codemode=false HTTP/1.1 200"}}
```

This correlation is what allows request-level latency to be tied to authentication and tool activity despite the absence of a trace backend.

### 8.3 Query Activity

```bash
gcloud logging read \
  'logName="projects/jor-mcp/logs/run.googleapis.com%2Fstdout"
   AND jsonPayload.message="WordPress search completed"' \
  --limit=20000 --format=json
```

Representative entry:

```json
{
  "jsonPayload": {
    "logger": "src.tools",
    "message": "WordPress search completed",
    "extra": {"query": "grilagem Bahia", "result_count": 2}
  },
  "timestamp": "2026-10-22T19:52:37.343019Z"
}
```

### 8.4 Cloud Monitoring Queries

`gcloud monitoring` does not expose time series, so the values were read from the Monitoring REST API:

```bash
TOKEN=$(gcloud auth print-access-token)

curl -sG "https://monitoring.googleapis.com/v3/projects/jor-mcp/timeSeries" \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode 'filter=metric.type="run.googleapis.com/request_latencies"
    AND resource.labels.service_name="jor-mcp-server"' \
  --data-urlencode 'interval.startTime=2026-09-25T20:28:36Z' \
  --data-urlencode 'interval.endTime=2026-10-25T20:55:00Z' \
  --data-urlencode 'aggregation.alignmentPeriod=2592000s' \
  --data-urlencode 'aggregation.perSeriesAligner=ALIGN_PERCENTILE_95' \
  --data-urlencode 'aggregation.crossSeriesReducer=REDUCE_PERCENTILE_95'
```

Swap `metric.type` and the aggregation per metric:

| Metric | Per-series aligner | Cross-series reducer |
|---|---|---|
| `request_count` | `ALIGN_SUM` | `REDUCE_SUM` |
| `request_latencies` | `ALIGN_PERCENTILE_95` | `REDUCE_PERCENTILE_95` |
| `container/startup_latencies` | `ALIGN_PERCENTILE_95` | `REDUCE_PERCENTILE_95` |
| `container/cpu/utilizations` | `ALIGN_PERCENTILE_95` | `REDUCE_PERCENTILE_95` |
| `container/memory/utilizations` | `ALIGN_PERCENTILE_95` | `REDUCE_PERCENTILE_95` |
| `container/instance_count` | `ALIGN_MAX` | `REDUCE_MAX` |

### 8.5 Resource Utilisation

| Metric | 30-day value |
|---|---|
| Container startup latency p95 | 24.03 s |
| CPU utilisation p95 | 2.0% of allocated vCPU |
| Memory utilisation p95 | 30.0% of 1 GiB |
| Maximum instances observed | 5 (configured ceiling) |

### 8.6 Public Health Probe

```bash
curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' \
  https://jormcp.ambiental.media/api/oauth/health
# 200 0.804140s (re-probe: 200 1.082923s)
```

`/health` returns 404 through the load balancer because only `/mcp*` and `/api/oauth*` are routed to Cloud Run; `/api/oauth/health` is the reachable health endpoint.

## 9. Limitations

- **30-day ceiling.** Cloud Logging retention caps the window; no pre-September baseline exists in stored telemetry.
- **No exported traces.** `OTEL_TRACES_EXPORTER` is unset in the deployed revision, so span data is unavailable. All latency figures come from request logs.
- **No per-tool timing.** Application logs record query text and result count, but not tool duration, so WordPress and GitHub time cannot be separated from total request time.
- **Search sample is small.** 28 searches over 30 days is enough for proxies, not for a precision percentage. Most traffic is handshake and listing calls rather than substantive queries.
- **Availability has no probe history.** Uptime checks were never configured, so availability is reconstructed from request logs; a period with zero traffic would appear as 100% availability by absence of failures, not by evidence of health.
- **Scanner-heavy tail.** 87.6% of requests are unauthenticated probing. Any metric computed over raw request counts must state whether scanners are included.
- **Cold start not in request latency.** The 24.03 s p95 startup time is reported separately and is not part of the 1.03 s mean.
- **Counts are a point-in-time extraction.** The service keeps receiving traffic during analysis, so totals can differ by a few requests between queries.

## 10. Recommended Measurement Next Steps

No implementation was performed for this report. If the indicators become contractual, the gaps above define the minimum instrumentation work:

| Gap | Minimum change |
|---|---|
| Per-tool latency and error rate | Emit `duration_ms` and `tool` fields in tool logs, then derive log-based metrics |
| Trace visibility | Set `OTEL_TRACES_EXPORTER=otlp` with a reachable collector |
| Availability history | Configure an uptime check on `/api/oauth/health` and an alert policy on the 5xx ratio |
| Precision | Build a golden query set with relevance judgments, evaluated offline |
| Freshness | Log the WordPress `modified` timestamp at fetch time and compare it with the response timestamp |

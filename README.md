# **Apillm Gateway**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/)

**Apillm Gateway** (API LLM Gateway) is an enterprise-grade reverse proxy and cost control gateway designed for Large Language Model (LLM) APIs. It sits transparently between your application microservices and third-party LLM providers (e.g., OpenAI, Anthropic, Gemini) to enforce security policies and slash API consumption costs.

---

## **Key Features**

1. **Zero Data Leakage (PII Redaction)**: Scrutinizes inbound prompt requests using configurable regex patterns to strip out sensitive data (emails, credit card numbers, US SSNs, and cloud credentials/API tokens) prior to forwarding requests upstream.
2. **Direct Billing Optimization (SQLite Caching)**: High-speed caching saves outbound token billing on repeated prompt queries. Features dynamic whitespace/casing prompt normalization and configurable Time-to-Live (TTL) cache invalidation.
3. **Budget Governance (Access Control & Rate Limiting)**: Validates client identities via Bearer tokens and applies rolling rate limits to prevent runaway loops or developer budget overruns.
4. **Resilient Upstream Failover**: If the primary LLM provider fails, Apillm automatically reroutes queries to a designated fallback provider to guarantee service availability.
5. **Telemetry Dashboard**: A dark-theme, glassmorphic visual command center to monitor live cache hit ratios, token metrics, cost savings, and redact events in real-time. Includes an interactive testing console.

---

## **Architecture Workflow**

```mermaid
flowchart TD
    Client[Client App] -->|Bearer Auth Header| Proxy[Apillm Proxy]
    Proxy -->|Validate Key & RPM Limit| Auth{Auth & Rate Limit}
    Auth -->|Failed| FailRes[401 / 429 Error]
    Auth -->|Success| Scrub[PII Scrubber Engine]
    Scrub -->|Strip PII| CacheCheck{Cache Lookup}
    CacheCheck -->|Cache HIT| ReturnCache[Return Cached Response + Update Savings Stats]
    CacheCheck -->|Cache MISS| RouteUpstream[Route to Default/Target Provider]
    RouteUpstream -->|Fetch Response| StoreCache[Write to SQLite Cache]
    StoreCache --> ReturnRes[Return Response to Client]
```

---

## **Telemetry Command Center UI**

Below is a live walkthrough and interface view of the Apillm Gateway admin dashboard during execution:

### **Live Interactive Walkthrough**
Here is a screen recording demonstrating real-time logs, security filter redactions, and cache hit metrics increments:

![Apillm Gateway Walkthrough](assets/dashboard_walkthrough.webp)

### **Visual Telemetry Overview**
![Apillm Gateway Dashboard](assets/dashboard_screenshot.png)

---

## **Project Structure**

```text
apillm-gateway/
├── dashboard/
│   └── index.html          # HTML5 Glassmorphism dashboard interface
├── apillm/
│   ├── __init__.py
│   ├── auth.py             # Client keys validation & rate limits
│   ├── cache.py            # SQLite caching logic
│   ├── config.py           # Config loader (reads config.json)
│   ├── logger.py           # Metrics aggregation & audit trail
│   ├── proxy.py            # Core FastAPI server & telemetry APIs
│   └── scrubber.py         # Regex PII scrubbing engine
├── config.json             # Central configuration panel
├── mock_provider.py        # Mock OpenAI-compatible LLM provider
├── run.py                  # Environment setup & server launcher
├── test_suite.py           # Integration test suite
├── requirements.txt        # Third-party dependencies
└── .gitignore              # Ignored local logs, databases & environments
```

---

## **Getting Started**

### **Prerequisites**
- **Python 3.10+** (Recommended)
- **pip** package installer

### **Quickstart Setup**
The simplest way to spin up the entire Apillm ecosystem is using the auto-setup launcher script. This script automatically handles Python virtual environment creation, dependencies installation (FastAPI, Uvicorn, Requests), and launches both the gateway and a mock LLM provider:

```bash
# Clone the repository (or copy folders)
cd apillm-gateway

# Start servers
python3 run.py
```

Upon a successful launch, you will see output like:
```text
============================================================
 Apillm Gateway Sentinel is fully operational!
  - Gateway Endpoint:  http://127.0.0.1:8090/v1/chat/completions
  - Admin Dashboard:   http://127.0.0.1:8090/dashboard
  - Upstream Provider: http://127.0.0.1:8095/v1/chat/completions
============================================================
```

To view metrics, navigate your browser to **[http://127.0.0.1:8090/dashboard](http://127.0.0.1:8090/dashboard)**.

---

## **Running Integration Tests**

We provide an automated verification suite to test authorization, PII filtering, caching, rate-limit headers, upstream failovers, and telemetry API:

```bash
# Run tests inside the virtualenv environment
.venv/bin/python test_suite.py
```

---

## **Configuration Guide (`config.json`)**

You can customize the proxy ports, providers, API keys, rate limits, and custom redact patterns directly in `config.json`:

```json
{
  "proxy": {
    "host": "127.0.0.1",
    "port": 8090,
    "dashboard_enabled": true
  },
  "upstream": {
    "default_provider": "mock-api",
    "fallback_provider": "mock-api",
    "providers": {
      "mock-api": {
        "url": "http://127.0.0.1:8095/v1/chat/completions",
        "api_key": "mock-key-123"
      }
    }
  },
  "caching": {
    "enabled": true,
    "type": "sqlite",
    "database_path": "apillm_cache.db",
    "ttl_seconds": 3600
  },
  "security": {
    "redaction_enabled": true,
    "redact_replacement": "[REDACTED_{rule_name}]",
    "rules": [
      {
        "name": "EMAIL",
        "pattern": "[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+",
        "enabled": true
      }
    ]
  }
}
```

- **`upstream.providers`**: Map target LLM endpoints (e.g. OpenAI production urls) and configure their outbound API authentication keys.
- **`security.rules`**: Define custom regular expressions to match sensitive identifiers. Any matched text will be scrubbed prior to leaving the gateway.

---

## **License**

Distributed under the MIT License. See [LICENSE](LICENSE) for more details.

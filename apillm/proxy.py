import json
import urllib.request
import urllib.error
import time
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

from apillm.config import config
from apillm.scrubber import scrubber
from apillm.cache import cache
from apillm.auth import auth
from apillm.logger import logger

app = FastAPI(title="Apillm Gateway", version="1.0.0")

# Setup static files directory for the dashboard
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dashboard_dir = os.path.join(base_dir, "dashboard")

# Route for dashboard root HTML
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    index_path = os.path.join(dashboard_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return f.read()
    return "<h3>Dashboard page not found. Please verify the dashboard path.</h3>"

# Mount remaining dashboard static files (js, css)
if os.path.exists(dashboard_dir):
    app.mount("/dashboard/static", StaticFiles(directory=dashboard_dir), name="static")

def extract_prompt_content(payload: dict) -> tuple[str, bool]:
    """
    Extracts content string from the payload.
    Supports classic 'prompt' string and modern 'messages' array.
    Returns: (extracted_text, is_messages_format)
    """
    if "prompt" in payload:
        return payload["prompt"], False
        
    if "messages" in payload and isinstance(payload["messages"], list):
        # Concatenate message contents for unified cache & redaction checks
        contents = []
        for msg in payload["messages"]:
            if isinstance(msg, dict) and "content" in msg:
                contents.append(msg["content"])
        return "\n".join(contents), True
        
    return "", False

def inject_scrubbed_content(payload: dict, scrubbed_text: str, is_messages_format: bool) -> dict:
    """
    Re-injects scrubbed text into payload matching original format.
    """
    if not is_messages_format:
        payload["prompt"] = scrubbed_text
        return payload
        
    # For messages format, split by newline or reconstruct.
    # To keep it perfect, we can scrub each message individually instead of concatenating.
    # Let's perform individual scrubbing inside proxy endpoint for accuracy.
    return payload

def normalize_prompt(text: str) -> str:
    import re
    cleaned = text.strip().lower()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned

def calculate_model_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = config.get("pricing", default={})
    profile = pricing.get(model_name, pricing.get("default", {
        "input_cost_per_1k": 0.0015,
        "output_cost_per_1k": 0.0020
    }))
    
    in_rate = profile.get("input_cost_per_1k", 0.0015)
    out_rate = profile.get("output_cost_per_1k", 0.0020)
    
    cost = (prompt_tokens * in_rate / 1000.0) + (completion_tokens * out_rate / 1000.0)
    return cost

def forward_request(provider_config: dict, payload: dict) -> dict:
    import urllib.request
    import json
    
    upstream_url = provider_config.get("url")
    provider_api_key = provider_config.get("api_key")
    
    headers = {
        "Content-Type": "application/json"
    }
    if provider_api_key:
        headers["Authorization"] = f"Bearer {provider_api_key}"

    req_body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        upstream_url,
        data=req_body,
        headers=headers,
        method="POST"
    )
    
    with urllib.request.urlopen(req) as response:
        res_body = response.read()
        return json.loads(res_body.decode("utf-8"))


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

@app.post("/v1/chat/completions")
async def chat_completions(request: Request, response: Response):
    client_ip = request.client.host if request.client else "127.0.0.1"
    
    # 1. API Key Authentication
    auth_header = request.headers.get("Authorization", "")
    api_key = ""
    if auth_header.startswith("Bearer "):
        api_key = auth_header.split(" ")[1]
        
    if not auth.validate_key(api_key):
        logger.log_request(
            api_key=api_key, client_ip=client_ip, provider="unknown",
            prompt_len=0, scrubbed_prompt="", detections=[],
            cache_hit=False, cost=0.0, tokens=0, status_code=401
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key."
        )
        
    # 2. Rate Limiting
    is_limited, requests_left = auth.is_rate_limited(api_key)
    if is_limited:
        logger.log_request(
            api_key=api_key, client_ip=client_ip, provider="unknown",
            prompt_len=0, scrubbed_prompt="", detections=[],
            cache_hit=False, cost=0.0, tokens=0, status_code=429
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again in a minute."
        )
        
    response.headers["X-RateLimit-Remaining"] = str(requests_left)

    # Read payload
    try:
        body = await request.body()
        payload = json.loads(body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {e}")

    # 3. PII Scrubbing
    # Determine format
    original_text, is_messages = extract_prompt_content(payload)
    
    detections = []
    if is_messages:
        # Scrub each message content individually to preserve metadata structure
        for i, msg in enumerate(payload.get("messages", [])):
            if isinstance(msg, dict) and "content" in msg:
                scrubbed_content, msg_detections = scrubber.scrub(msg["content"])
                payload["messages"][i]["content"] = scrubbed_content
                detections.extend(msg_detections)
        # Re-extract scrubbed representation for caching key
        scrubbed_text, _ = extract_prompt_content(payload)
    else:
        scrubbed_text, detections = scrubber.scrub(original_text)
        payload["prompt"] = scrubbed_text

    # Print to console for proxy runtime logs
    if detections:
        print(f"[Apillm Proxy] PII Detected! Detections: {detections}", flush=True)

    # 4. Cache Interception (Normalized Prompt Caching)
    cache_key = normalize_prompt(scrubbed_text)
    cached_val = cache.get(cache_key)
    if cached_val:
        print(f"[Apillm Proxy] Cache HIT (Normalized match). Returning cached payload.", flush=True)
        cost_str = str(cached_val.get("billing_cost", "$0.00"))
        cost = float(cost_str.replace("$", "")) if isinstance(cost_str, str) else float(cost_str)
        
        usage = cached_val.get("usage", {})
        tokens = usage.get("total_tokens", 0) if isinstance(usage, dict) else cached_val.get("tokens_used", 0)
        
        logger.log_request(
            api_key=api_key, client_ip=client_ip, provider=config.get("upstream", "default_provider"),
            prompt_len=len(scrubbed_text), scrubbed_prompt=scrubbed_text, detections=detections,
            cache_hit=True, cost=cost, tokens=tokens, status_code=200
        )
        return cached_val

    # 5. Cache Miss: Route & Forward with Upstream Failover Resilience
    provider_name = request.headers.get("X-Provider", config.get("upstream", "default_provider"))
    providers = config.get("upstream", "providers", {})
    provider_config = providers.get(provider_name)
    
    if not provider_config:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider_name}' is not configured in Gateway."
        )

    print(f"[Apillm Proxy] Cache MISS. Forwarding request to Upstream Provider '{provider_name}'...", flush=True)
    
    upstream_res_json = None
    actual_provider = provider_name
    
    try:
        upstream_res_json = forward_request(provider_config, payload)
    except Exception as e:
        print(f"[Apillm Proxy] Upstream Provider '{provider_name}' failed: {e}. Checking for fallback failover...", flush=True)
        fallback_name = config.get("upstream", "fallback_provider")
        if fallback_name and fallback_name in providers and fallback_name != provider_name:
            fallback_config = providers.get(fallback_name)
            try:
                print(f"[Apillm Proxy] Routing to Fallback Upstream: '{fallback_name}'...", flush=True)
                upstream_res_json = forward_request(fallback_config, payload)
                actual_provider = fallback_name
                print(f"[Apillm Proxy] Fallback routing succeeded!", flush=True)
            except Exception as fe:
                logger.log_request(
                    api_key=api_key, client_ip=client_ip, provider=provider_name,
                    prompt_len=len(scrubbed_text), scrubbed_prompt=scrubbed_text, detections=detections,
                    cache_hit=False, cost=0.0, tokens=0, status_code=502
                )
                raise HTTPException(status_code=502, detail=f"All upstream routes failed. Primary error: {str(e)}. Fallback error: {str(fe)}")
        else:
            logger.log_request(
                api_key=api_key, client_ip=client_ip, provider=provider_name,
                prompt_len=len(scrubbed_text), scrubbed_prompt=scrubbed_text, detections=detections,
                cache_hit=False, cost=0.0, tokens=0, status_code=502
            )
            raise HTTPException(status_code=502, detail=f"Upstream provider failed and no fallback configured. Error: {str(e)}")

    # 6. Parse response, compute exact model-specific cost, and Cache
    try:
        usage = upstream_res_json.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", len(scrubbed_text.split()))
        completion_tokens = usage.get("completion_tokens", 25)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
        
        # Exact model pricing calculation
        model_name = upstream_res_json.get("model", payload.get("model", "default"))
        cost = calculate_model_cost(model_name, prompt_tokens, completion_tokens)
        
        upstream_res_json["billing_cost"] = f"${cost:.5f}"
        upstream_res_json["tokens_used"] = total_tokens
        
        # Save in persistent cache
        cache.set(cache_key, upstream_res_json, tokens_used=total_tokens, billing_cost=cost)
        
        # Log telemetry stats
        logger.log_request(
            api_key=api_key, client_ip=client_ip, provider=actual_provider,
            prompt_len=len(scrubbed_text), scrubbed_prompt=scrubbed_text, detections=detections,
            cache_hit=False, cost=cost, tokens=total_tokens, status_code=200
        )
        
        return upstream_res_json
        
    except Exception as e:
        logger.log_request(
            api_key=api_key, client_ip=client_ip, provider=actual_provider,
            prompt_len=len(scrubbed_text), scrubbed_prompt=scrubbed_text, detections=detections,
            cache_hit=False, cost=0.0, tokens=0, status_code=500
        )
        raise HTTPException(status_code=500, detail=f"Proxy processing error: {str(e)}")

# Telemetry API for the Dashboard
@app.get("/api/stats")
async def get_stats():
    return logger.get_stats()

@app.get("/api/logs")
async def get_logs(limit: int = 20):
    return logger.get_recent_logs(limit)

@app.post("/api/cache/clear")
async def clear_cache():
    cache.clear()
    return {"message": "Cache successfully cleared."}

@app.get("/api/keys")
async def get_keys():
    return auth.keys

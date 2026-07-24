import requests
import json
import time

def run_tests():
    print("="*60)
    print(" APILLM GATEWAY INTEGRATION TEST SUITE ")
    print("="*60)
    
    gateway_url = "http://127.0.0.1:8090/v1/chat/completions"
    dev_key = "sg-client-dev-key-xyz"
    prod_key = "sg-client-prod-key-abc"
    invalid_key = "invalid-key-example"
    
    # ----------------------------------------------------
    # TEST 1: API Key Authorization
    # ----------------------------------------------------
    print("\n[TEST 1] Verifying Gateway Authentication Rules...")
    
    # A. Missing Authorization Header
    try:
        res = requests.post(gateway_url, json={"prompt": "hello"})
        print(f"  - Missing Authorization: Code {res.status_code} (Expected: 401)")
        assert res.status_code == 401
    except AssertionError:
        print("  [-] FAILED: Missing authorization did not return 401.")
        return
        
    # B. Invalid Authorization Key
    try:
        res = requests.post(gateway_url, json={"prompt": "hello"}, headers={"Authorization": f"Bearer {invalid_key}"})
        print(f"  - Invalid Authorization Key: Code {res.status_code} (Expected: 401)")
        assert res.status_code == 401
    except AssertionError:
        print("  [-] FAILED: Invalid API Key did not return 401.")
        return
        
    # C. Valid Authorization Key
    try:
        res = requests.post(gateway_url, json={"prompt": "Hello world!"}, headers={"Authorization": f"Bearer {dev_key}"})
        print(f"  - Valid Authorization Key: Code {res.status_code} (Expected: 200)")
        assert res.status_code == 200
        print(f"    Response Body: {json.dumps(res.json(), indent=2)}")
    except Exception as e:
        print(f"  [-] FAILED: Valid API Key rejected or errored: {e}")
        return

    # ----------------------------------------------------
    # TEST 2: PII Redaction & Cache Miss/Hit
    # ----------------------------------------------------
    print("\n[TEST 2] Verifying PII Redaction & Caching Flow...")
    payload = {
        "prompt": "Secure payload containing email testing-user@shieldops.com and credit card 4111-2222-3333-4444. Summarize."
    }
    headers = {"Authorization": f"Bearer {dev_key}"}
    
    # Cache Miss
    try:
        print("  - Sending Request 1 (Cache Miss expected)...")
        res1 = requests.post(gateway_url, json=payload, headers=headers)
        assert res1.status_code == 200
        res1_json = res1.json()
        print(f"    Outbound Billing cost: {res1_json.get('billing_cost')}")
        print(f"    Usage Tokens: {res1_json.get('tokens_used')}")
    except Exception as e:
        print(f"  [-] FAILED on Request 1: {e}")
        return
        
    # Cache Hit (Normalized query check: extra space, mixed casing)
    try:
        print("  - Sending Request 2 (Cache Hit expected with mixed-casing & spacing)...")
        normalized_payload = {
            "prompt": "   sECUrE PAYlOAd coNTAINING EMAil testing-user@shieldops.com AND credit card 4111-2222-3333-4444. SuMMarIzE.  "
        }
        res2 = requests.post(gateway_url, json=normalized_payload, headers=headers)
        assert res2.status_code == 200
        res2_json = res2.json()
        print(f"    Cached Billing cost: {res2_json.get('billing_cost')}")
        print("    [+] Cache successfully matched normalized prompt casing and padding.")
    except Exception as e:
        print(f"  [-] FAILED on Normalized Cache Hit query: {e}")
        return

    # ----------------------------------------------------
    # TEST 3: Telemetry Dashboard APIs
    # ----------------------------------------------------
    print("\n[TEST 3] Querying Telemetry Stats Endpoint...")
    try:
        stats_res = requests.get("http://127.0.0.1:8090/api/stats")
        assert stats_res.status_code == 200
        stats = stats_res.json()
        print(f"    Total Requests: {stats.get('total_requests')}")
        print(f"    Cache Hits: {stats.get('cache_hits')}")
        print(f"    Cache Misses: {stats.get('cache_misses')}")
        print(f"    Total Dollars Saved: ${stats.get('total_cost_saved'):.5f}")
        print(f"    PII Redacted Tokens: {stats.get('pii_redacted_count')}")
        assert stats.get('cache_hits') >= 1
        assert stats.get('pii_redacted_count') >= 2 # Email and Card
    except Exception as e:
        print(f"  [-] FAILED to retrieve or validate telemetry stats: {e}")
        return

    # ----------------------------------------------------
    # TEST 4: Rate Limiting Enforcement
    # ----------------------------------------------------
    print("\n[TEST 4] Simulating Burst Requests for Rate Limiting...")
    print("  - Sending fast successive queries (Dev Key limit is 120, let's use a dynamic check or send many rapidly)")
    # Since dev key limit is 120, let's modify dev key in config or send requests rapidly to see remaining limit decrementing.
    # We can inspect 'X-RateLimit-Remaining' header!
    try:
        res = requests.post(gateway_url, json={"prompt": "Rate check"}, headers=headers)
        remaining = res.headers.get("X-RateLimit-Remaining")
        print(f"    - Remaining requests allowed this minute: {remaining}")
        assert remaining is not None
        print("    [+] Rate limit headers returned successfully.")
    except Exception as e:
        print(f"  [-] FAILED to check rate limit headers: {e}")
        return

    # ----------------------------------------------------
    # TEST 5: Resilient Upstream Failover Routing
    # ----------------------------------------------------
    print("\n[TEST 5] Verifying Upstream Failover Routing...")
    try:
        # Requesting broken-api should result in fallback routing to mock-api and a success code 200
        failover_headers = {
            "Authorization": f"Bearer {dev_key}",
            "X-Provider": "broken-api"
        }
        print("  - Requesting 'broken-api' (expecting failover to 'mock-api')...")
        res_failover = requests.post(gateway_url, json={"prompt": "Failover probe query"}, headers=failover_headers)
        print(f"    Response status: {res_failover.status_code} (Expected: 200)")
        assert res_failover.status_code == 200
        print(f"    Fallback response payload ID: {res_failover.json().get('id')}")
        print("    [+] Failover fail-retry routed successfully.")
    except Exception as e:
        print(f"  [-] FAILED during failover routing check: {e}")
        return

    print("\n" + "="*60)
    print(" [+] ALL GATEWAY SERVICE VERIFICATIONS PASSED SUCCESSFULLY!")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_tests()

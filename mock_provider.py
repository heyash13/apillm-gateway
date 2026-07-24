from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import sys

class ShieldGuardMockProviderHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default standard log spam on stdout
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format%args))

    def do_POST(self):
        if self.path == "/v1/chat/completions":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                payload = json.loads(post_data.decode("utf-8"))
                
                # Support prompt or messages
                prompt_content = ""
                if "prompt" in payload:
                    prompt_content = payload["prompt"]
                elif "messages" in payload and isinstance(payload["messages"], list):
                    prompt_content = "\n".join([m.get("content", "") for m in payload["messages"] if isinstance(m, dict)])
                
                # Print received prompt to stdout for verification
                print(f"[Upstream Provider Received] Body: {prompt_content}", flush=True)
                
                # Simulate token usage
                prompt_tokens = len(prompt_content.split())
                completion_tokens = 25
                total_tokens = prompt_tokens + completion_tokens
                
                # Compute mock cost
                cost = (prompt_tokens * 0.000015) + (completion_tokens * 0.00002)
                
                response_data = {
                    "id": "chatcmpl-mock-12345",
                    "object": "chat.completion",
                    "created": 1677652288,
                    "model": "gpt-mock-llm-3.5-turbo",
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"Mock API Response: I received your request. The scrubbed metadata has length {len(prompt_content)}."
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens
                    },
                    "billing_cost": f"${cost:.5f}"
                }
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode("utf-8"))
                
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def run(port=8095):
    server_address = ('', port)
    httpd = HTTPServer(server_address, ShieldGuardMockProviderHandler)
    print(f"[*] Upstream Provider Mock LLM running on port {port}...", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("[*] Upstream Provider Mock LLM stopped.", flush=True)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8095
    run(port)

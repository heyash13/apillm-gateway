import os
import subprocess
import sys
import time

def setup_environment():
    print("[*] Apillm Gateway: Checking Environment...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(base_dir, ".venv")
    
    # Check if virtualenv exists
    if not os.path.exists(venv_dir):
        print("[*] Virtual environment not found. Creating virtual environment in .venv...")
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
        
    # Determine pip path based on platform
    if os.name == "nt":
        pip_path = os.path.join(venv_dir, "Scripts", "pip.exe")
        python_path = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        pip_path = os.path.join(venv_dir, "bin", "pip")
        python_path = os.path.join(venv_dir, "bin", "python")

    print("[*] Installing required dependencies (fastapi, uvicorn, requests)...")
    subprocess.check_call([pip_path, "install", "--upgrade", "pip", "--index-url", "https://pypi.org/simple"])
    subprocess.check_call([pip_path, "install", "fastapi", "uvicorn", "requests", "--index-url", "https://pypi.org/simple"])
    print("[+] Environment successfully set up.")
    return python_path

def main():
    python_path = setup_environment()
    
    try:
        # Start Apillm Proxy Gateway (via uvicorn)
        print("[*] Starting Apillm Gateway on port 8090...")
        proxy_proc = subprocess.Popen(
            [python_path, "-m", "uvicorn", "apillm.proxy:app", "--host", "127.0.0.1", "--port", "8090", "--log-level", "info"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        time.sleep(2)
        
        # Check if running
        if proxy_proc.poll() is not None:
            print("[-] Error: Apillm Proxy Gateway failed to start.")
            stdout, _ = proxy_proc.communicate()
            print(stdout)
            return
            
        print("\n" + "="*60)
        print(" Apillm Gateway is fully operational!")
        print("  - Gateway Endpoint: http://127.0.0.1:8090/v1/chat/completions")
        print("  - Admin Dashboard:  http://127.0.0.1:8090/dashboard")
        print("="*60 + "\n")
        print("[*] Press Ctrl+C to terminate gateway...\n")
        
        # Keep running
        while True:
            if proxy_proc.poll() is not None:
                print(f"[-] Gateway process terminated unexpectedly with code {proxy_proc.poll()}")
                break
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n[*] Shutting down Apillm Gateway...")
        try:
            proxy_proc.terminate()
            proxy_proc.wait(timeout=2)
        except Exception:
            proxy_proc.kill()
        print("[+] Done. Goodbye!")

if __name__ == "__main__":
    main()

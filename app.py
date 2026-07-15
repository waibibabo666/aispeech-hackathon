"""Desktop app launcher — native Windows window for 日知.

Usage:
    python app.py          # desktop mode (requires frontend/dist built)
    python app.py --dev    # development mode (needs Vite dev server running on :5173)
"""

import argparse
import asyncio
import sys
import threading
import time
from pathlib import Path

# On Windows, override ProactorEventLoop before ANY event loop is created.
# httpx (used by OpenAI SDK) is incompatible with ProactorEventLoop (IOCP)
# inside daemon threads — causes persistent "Connection error."
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ROOT = Path(__file__).resolve().parent
FRONTEND_INDEX = ROOT / "frontend" / "dist" / "index.html"


def kill_port(port: int) -> None:
    """Kill any process listening on the given port."""
    import subprocess
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                subprocess.run(["taskkill", "/PID", pid, "/F"],
                               capture_output=True, timeout=5)
    except Exception:
        pass


def start_backend(port: int = 8000) -> None:
    sys.path.insert(0, str(ROOT))
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port,
                reload=False, log_level="info")


def wait_for_backend(url: str, timeout: float = 10) -> bool:
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=0.5)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    parser = argparse.ArgumentParser(description="日知 Desktop")
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()

    if not args.dev and not FRONTEND_INDEX.exists():
        print("Frontend not built. Run: cd frontend && npm run build")
        sys.exit(1)

    backend_url = "http://127.0.0.1:8000"
    frontend_url = "http://localhost:5173" if args.dev else backend_url

    if not args.dev:
        # Clean up stale process
        kill_port(8000)

        print("Starting 日知...")
        threading.Thread(target=start_backend, daemon=True).start()
        if not wait_for_backend(f"{backend_url}/api/health"):
            print("ERROR: Backend failed to start (port 8000 may be in use).")
            sys.exit(1)
        print("Ready.")

    import webview

    print("Opening window...")
    try:
        webview.create_window(
            title="日知",
            url=frontend_url,
            width=1280,
            height=800,
            min_size=(900, 600),
        )
        webview.start()
    except Exception as e:
        print(f"Webview window failed: {e}")
        print("Falling back to browser...")
        import webbrowser
        webbrowser.open(frontend_url)
        print(f"Opened {frontend_url} in browser. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    print("Goodbye.")


if __name__ == "__main__":
    main()

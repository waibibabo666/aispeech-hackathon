"""FastAPI application entry point."""

import asyncio
import sys

# On Windows, override the default ProactorEventLoop — httpx (used by the
# OpenAI SDK) can fail with "Connection error." inside daemon-thread uvicorn
# when running under ProactorEventLoop (IOCP).  SelectorEventLoop is more
# compatible with httpx's connection pool.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .routers import upload, tasks, config

app = FastAPI(title="日知 API", version="0.1.0")

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(upload.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(config.router, prefix="/api")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "task-manager"}


@app.get("/api/network-check")
async def network_check():
    """Diagnostic: test outbound connectivity from within the server process."""
    import asyncio as _asyncio
    import socket
    import ssl
    import time as _time

    result: dict = {"tests": [], "event_loop": type(_asyncio.get_running_loop()).__name__}

    # Test 1: DNS resolution
    try:
        addrs = socket.getaddrinfo("apifusion.aispeech.com.cn", 443,
                                   socket.AF_INET, socket.SOCK_STREAM)
        ip = addrs[0][4][0] if addrs else "unknown"
        result["tests"].append({"dns": "ok", "ip": ip})
    except Exception as e:
        result["tests"].append({"dns": "FAIL", "error": str(e)})
        return result  # no point continuing

    # Test 2: Raw TCP connect (no TLS)
    t0 = _time.time()
    try:
        sock = socket.create_connection(("apifusion.aispeech.com.cn", 443), timeout=5)
        elapsed = _time.time() - t0
        result["tests"].append({"tcp": "ok", "elapsed_ms": int(elapsed * 1000)})
        sock.close()
    except Exception as e:
        result["tests"].append({"tcp": "FAIL", "error": f"{type(e).__name__}: {e}", "elapsed_ms": int((_time.time() - t0) * 1000)})
        return result

    # Test 3: httpx GET (async)
    import httpx
    try:
        async with httpx.AsyncClient(proxy=None, verify=True, timeout=10.0) as hc:
            resp = await hc.get("https://apifusion.aispeech.com.cn/v1/models")
            result["tests"].append({"httpx_api": "ok", "status": resp.status_code})
    except Exception as e:
        result["tests"].append({"httpx_api": "FAIL", "error": f"{type(e).__name__}: {e}"})
        if e.__cause__:
            result["tests"].append({"httpx_api_cause": f"{type(e.__cause__).__name__}: {e.__cause__}"})

    # Test 4: httpx to a public URL to verify general outbound HTTPS
    try:
        async with httpx.AsyncClient(proxy=None, verify=True, timeout=10.0) as hc:
            resp = await hc.get("https://httpbin.org/get")
            result["tests"].append({"httpx_public": "ok", "status": resp.status_code})
    except Exception as e:
        result["tests"].append({"httpx_public": "FAIL", "error": f"{type(e).__name__}: {e}"})

    return result


# Serve frontend static files in production
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


def main():
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )


if __name__ == "__main__":
    main()

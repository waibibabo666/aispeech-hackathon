"""日知 launcher — interactive menu for dev / desktop mode.

Double-click this file (or run `python launch.py`) to start.
No .bat file needed — fully in Python, no encoding issues.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / "venv" / "Scripts" / "python.exe"


def kill_port(port: int) -> None:
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


def build_frontend() -> None:
    print("Building frontend...")
    subprocess.run(["npm", "run", "build"], cwd=str(ROOT / "frontend"),
                   shell=True, check=True)
    print("Build done.\n")


def check_venv() -> None:
    if not VENV_PYTHON.exists():
        print("[ERROR] venv not found. Run: python -m venv venv")
        input("Press Enter to exit...")
        sys.exit(1)

    if not (ROOT / "frontend" / "node_modules").exists():
        print("Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=str(ROOT / "frontend"),
                       shell=True, check=True)


def menu() -> str:
    print("=" * 45)
    print("  日知")
    print("=" * 45)
    print()
    print("  1. Dev mode    (Vite hot-reload + backend)")
    print("  2. Desktop     (native window)")
    print()
    choice = input("Choose [1 or 2]: ").strip()
    return choice


def run_dev() -> None:
    print("\nStarting Dev Mode...")
    print("  Backend:  http://localhost:8000")
    print("  Frontend: http://localhost:5173")
    print()

    subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "backend.main:app",
         "--host", "127.0.0.1", "--port", "8000", "--reload"],
        cwd=str(ROOT),
    )

    time.sleep(3)

    subprocess.run(
        ["npx", "vite", "--host"],
        cwd=str(ROOT / "frontend"),
        shell=True,
    )


def run_desktop() -> None:
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        build_frontend()

    print("\nStarting 日知 Desktop...\n")

    subprocess.run(
        [str(VENV_PYTHON), "app.py"],
        cwd=str(ROOT),
    )


def main() -> None:
    check_venv()

    # Clean stale processes
    kill_port(8000)
    kill_port(5173)

    choice = menu()

    if choice == "1":
        run_dev()
    elif choice == "2":
        run_desktop()
    else:
        print("Invalid choice, starting Desktop mode...")
        run_desktop()


if __name__ == "__main__":
    main()

"""一键启动开发环境 — 自动检测 venv，双击即可运行."""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def find_python() -> str:
    """找到 venv 里的 Python，没有 venv 就用当前 Python."""
    venv_python = ROOT / "venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def check_deps():
    """检查依赖是否安装，没装就自动安装."""
    print("检查依赖...")

    # 检查 Python 依赖
    try:
        import fastapi  # noqa: F401
    except ImportError:
        print("[安装] Python 依赖...")
        python = find_python()
        subprocess.run(
            [python, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=str(ROOT), check=True,
        )

    # 检查前端依赖
    if not (ROOT / "frontend" / "node_modules").exists():
        print("[安装] 前端依赖 (npm install)...")
        subprocess.run(
            ["npm", "install"], cwd=str(ROOT / "frontend"),
            shell=True, check=True,
        )

    print("依赖就绪 ✓\n")


def main():
    print("=" * 50)
    print("  日知 - 开发模式")
    print("  后端 API:  http://localhost:8000")
    print("  前端页面:  http://localhost:5173")
    print("  Ctrl+C 停止")
    print("=" * 50)
    print()

    check_deps()

    python = find_python()

    # 启动后端 (uvicorn with auto-reload)
    backend = subprocess.Popen(
        [python, "-m", "uvicorn", "backend.main:app",
         "--host", "127.0.0.1", "--port", "8000", "--reload"],
        cwd=str(ROOT),
    )

    # 启动前端 (Vite dev server with HMR)
    frontend = subprocess.Popen(
        ["npx", "vite", "--host"],
        cwd=str(ROOT / "frontend"),
        shell=True,  # Windows needs shell for npx.cmd
    )

    # 等后端启动后打开浏览器
    time.sleep(2)
    webbrowser.open("http://localhost:5173")

    try:
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        print("\n正在停止...")
        backend.terminate()
        frontend.terminate()
        print("已停止")


if __name__ == "__main__":
    main()

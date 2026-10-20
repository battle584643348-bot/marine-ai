"""启动入口：python run.py [--host 0.0.0.0] [--port 8000]"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

from backend.app.core.config import get_config  # noqa: E402


def main():
    cfg = get_config()
    host = cfg.get("server.host", "127.0.0.1")
    port = int(cfg.get("server.port", 8000))
    if "--host" in sys.argv:
        host = sys.argv[sys.argv.index("--host") + 1]
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    print(f"\n  ██ 海工智舱 Marine AI 启动中")
    print(f"  ██ 地址: http://{host}:{port}")
    print(f"  ██ 按 Ctrl+C 停止\n")
    uvicorn.run("backend.app.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

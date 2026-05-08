"""
Auralis - Startup Script
Run with: python run.py
"""

import os
import sys

# Force UTF-8 mode on Windows to prevent cp1252 codec errors
os.environ.setdefault("PYTHONUTF8", "1")
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,   # reload=True can cause double-startup; keep False for stability
        log_level="info",
    )

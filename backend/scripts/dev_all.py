"""Run the API server and the voice-agent worker side by side, no Docker.

voice_agent/ has its own venv (heavy deps: torch/faster-whisper/silero, kept out of
the main pyproject.toml — see voice_agent/agent.py's docstring). One-time setup:

    uv venv voice_agent/.venv
    uv pip install -r voice_agent/requirements.txt --python voice_agent/.venv/Scripts/python.exe

(POSIX: .venv/bin/python instead of .venv/Scripts/python.exe)
"""

import os
import subprocess
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
VOICE_AGENT_DIR = BACKEND_DIR / "voice_agent"
VOICE_AGENT_PYTHON = VOICE_AGENT_DIR / (
    ".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python"
)

if not VOICE_AGENT_PYTHON.exists():
    sys.exit(
        f"Missing venv: {VOICE_AGENT_PYTHON}\n"
        "One-time setup:\n"
        "  uv venv voice_agent/.venv\n"
        f"  uv pip install -r voice_agent/requirements.txt --python {VOICE_AGENT_PYTHON}"
    )

procs = [
    subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--reload"], cwd=BACKEND_DIR),
    subprocess.Popen([str(VOICE_AGENT_PYTHON), "agent.py", "dev"], cwd=VOICE_AGENT_DIR),
]

try:
    while all(p.poll() is None for p in procs):
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    for p in procs:
        p.terminate()
    for p in procs:
        p.wait()

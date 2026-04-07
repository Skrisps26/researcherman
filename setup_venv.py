#!/usr/bin/env python3
"""Bootstrap: create a Python venv and install all dependencies.

Usage:
    python3 setup_venv.py               # from the project root
"""

import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_ROOT, "venv")
PIP = os.path.join(VENV_DIR, "bin", "pip")
REQUIREMENTS = os.path.join(PROJECT_ROOT, "requirements.txt")


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print(f"  >>  {' '.join(cmd)}")
    return subprocess.run(cmd, check=check)


def main() -> None:
    # 1. Create venv
    print("[1/3] Creating virtual environment...")
    run([sys.executable, "-m", "venv", VENV_DIR])

    # 2. Upgrade pip
    print("[2/3] Upgrading pip inside venv...")
    run([PIP, "install", "--upgrade", "pip"])

    # 3. Install requirements
    print("[3/3] Installing dependencies...")
    run([PIP, "install", "-r", REQUIREMENTS])

    print("\n✅  Setup complete.")
    print(f"    Activate with: source {VENV_DIR}/bin/activate")


if __name__ == "__main__":
    main()

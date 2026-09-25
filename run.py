"""
Synapse — Launcher Script

Starts both backend (port 8000) and frontend (port 3000).
Usage: python run.py
"""
import subprocess
import sys
import os
import signal
import time


def main():
    print("=" * 50)
    print("  SYNAPSE - Railway ETA Intelligence")
    print("  SIH26028 - Smart India Hackathon 2026")
    print("=" * 50)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(base_dir, "backend")
    frontend_dir = os.path.join(base_dir, "frontend")

    processes = []

    try:
        # Start backend
        print("\n[1/2] Starting backend on http://localhost:8000 ...")
        backend = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=backend_dir,
        )
        processes.append(("Backend", backend))

        # Wait for backend to load
        print("      Waiting for backend to load data (~15s)...")
        time.sleep(15)

        # Start frontend
        print("[2/2] Starting frontend on http://localhost:3000 ...")
        frontend = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_dir,
            shell=True,
        )
        processes.append(("Frontend", frontend))

        print("\n" + "=" * 50)
        print("  Backend:  http://localhost:8000")
        print("  Frontend: http://localhost:3000")
        print("  API docs: http://localhost:8000/docs")
        print("=" * 50)
        print("\n  Press Ctrl+C to stop both services.\n")

        # Wait for either to exit
        while True:
            for name, proc in processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"\n{name} exited with code {ret}")
                    raise KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
        for name, proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=5)
                print(f"  {name} stopped.")
            except Exception:
                proc.kill()
                print(f"  {name} killed.")


if __name__ == "__main__":
    main()

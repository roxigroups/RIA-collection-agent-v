import contextlib
import os
import shutil
import signal
import socket
import subprocess
import sys
import time

API_PORT = 5001


def port_in_use(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def agent_running() -> bool:
    return subprocess.run(["pgrep", "-f", "agent.py start"], capture_output=True).returncode == 0


def run():
    print("🚀 Starting RIA invoice agent...")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(base_dir, "..", "frontend")
    agent_path = os.path.join(base_dir, "agent.py")
    server_path = os.path.join(base_dir, "server.py")
    frontend_port = os.getenv("FRONTEND_PORT", "3000")

    commands = {}
    # 1. The LiveKit voice agent worker (one process per call)
    if agent_running():
        print("✅ LiveKit agent already running; not starting a second one.")
    else:
        commands["LiveKit agent (agent.py)"] = ([sys.executable, agent_path, "start"], base_dir)
    # 2. The API and the dialer (127.0.0.1:5001; the dashboard forwards /api here)
    if port_in_use(API_PORT):
        print(f"✅ API server already running on port {API_PORT}.")
    else:
        commands["API server (server.py)"] = ([sys.executable, server_path], base_dir)
    # 3. The dashboard (Next.js). Dev mode by default, so it always shows the current code;
    # RIA_DASHBOARD=build serves the production build made by `npm run build`
    npm = shutil.which("npm")
    if port_in_use(int(frontend_port)):
        print(f"✅ Dashboard already running on port {frontend_port}.")
    elif not npm or not os.path.isdir(os.path.join(frontend_dir, "node_modules")):
        print("⚠️ Dashboard not started: install Node.js and run `npm ci` in frontend/ first.")
    elif os.getenv("RIA_DASHBOARD") == "build" and os.path.isfile(os.path.join(frontend_dir, ".next", "BUILD_ID")):
        commands["Dashboard (frontend, Next.js)"] = ([npm, "start", "--", "-p", frontend_port], frontend_dir)
    else:
        commands["Dashboard (frontend, Next.js)"] = ([npm, "run", "dev", "--", "-p", frontend_port], frontend_dir)

    def launch(cmd, cwd):
        # Own process group: stopping it also stops what it started (next-server, call processes)
        return subprocess.Popen(cmd, cwd=cwd, start_new_session=True)

    def stop(*_):
        raise KeyboardInterrupt

    # Ctrl+C, or `pkill -f start.py` when it runs in the background (which ignores Ctrl+C's signal)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    processes = {}
    for name, (cmd, cwd) in commands.items():
        print(f"▶️ Launching {name}...")
        processes[name] = launch(cmd, cwd)
    if commands:
        print(f"🌐 Dashboard: http://localhost:{frontend_port}   (Ctrl+C stops what this started)")

    try:
        # Keep every process running and restart any that stops
        while True:
            time.sleep(2)
            for name, (cmd, cwd) in commands.items():
                if processes[name].poll() is not None:
                    print(f"⚠️ {name} stopped. Restarting in 5 s...")
                    time.sleep(5)
                    processes[name] = launch(cmd, cwd)
    except KeyboardInterrupt:
        print("🛑 Stopping all processes...")
        for process in processes.values():
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
        deadline = time.monotonic() + 10
        for process in processes.values():
            try:
                process.wait(max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)


if __name__ == "__main__":
    run()

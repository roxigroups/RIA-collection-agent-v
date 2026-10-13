"""RIA voice agent worker: `python agent.py start` for live calls, `dev` to test.

The agent itself lives in ria/ (see ria/__init__.py for how a call works).
"""
import os

from livekit.agents import JobExecutorType, WorkerOptions, cli

from ria.call import entrypoint, prewarm

# Calls this worker takes at once: the dialer's limit, plus one for a customer calling in
MAX_CALLS = max(1, int(os.getenv("DIALER_CONCURRENCY", "1"))) + 1


def calls_load(worker) -> float:
    # Busy by calls, not by the Mac's CPU: LiveKit's default turned calls away whenever the
    # whole Mac passed 70% CPU (IDE, browser, dashboard dev server), and the customer
    # picked up to silence
    return min(len(worker.active_jobs) / MAX_CALLS, 1.0)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            load_fnc=calls_load,
            # Each call in its own process: a crash in LiveKit's native library then
            # ends only that call instead of the whole worker
            job_executor_type=JobExecutorType.PROCESS,
        )
    )

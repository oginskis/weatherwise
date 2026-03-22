"""Single entry point to start Weather MCP, News MCP, and Streamlit."""

from __future__ import annotations

import logging
import signal
import subprocess
import sys
import time
from types import FrameType

import httpx
from dotenv import load_dotenv

from src.agent.config import NEWS_MCP_PORT, STREAMLIT_PORT, WEATHER_MCP_PORT

load_dotenv()

logger = logging.getLogger(__name__)

HEALTH_CHECK_TIMEOUT_SECONDS: float = 30.0
HEALTH_CHECK_INTERVAL_SECONDS: float = 1.0


def _start_weather_mcp() -> subprocess.Popen[bytes]:
    """Start the weather MCP server."""
    logger.info("Starting weather MCP server on port %d...", WEATHER_MCP_PORT)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "mcp_weather_server",
            "--mode",
            "streamable-http",
            "--port",
            str(WEATHER_MCP_PORT),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _start_news_mcp() -> subprocess.Popen[bytes]:
    """Start the news MCP server."""
    logger.info("Starting news MCP server on port %d...", NEWS_MCP_PORT)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "src.mcp_servers.news.server",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _start_streamlit() -> subprocess.Popen[bytes]:
    """Start the Streamlit app."""
    logger.info("Starting Streamlit on port %d...", STREAMLIT_PORT)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "src/ui/app.py",
            "--server.port",
            str(STREAMLIT_PORT),
            "--server.headless",
            "true",
        ],
    )


def _wait_for_server(port: int, name: str) -> bool:
    """Wait until a server responds on the given port."""
    url = f"http://localhost:{port}/mcp"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    deadline = time.monotonic() + HEALTH_CHECK_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            response = httpx.post(
                url,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "id": 1,
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "health-check", "version": "0.1.0"},
                    },
                },
                timeout=5.0,
            )
            if response.status_code in (200, 400, 405, 406):
                logger.info("%s is ready on port %d (status=%d)", name, port, response.status_code)
                return True
        except httpx.HTTPError:
            pass
        time.sleep(HEALTH_CHECK_INTERVAL_SECONDS)
    logger.error("%s failed to start on port %d", name, port)
    return False


def main() -> None:
    """Start all services and manage their lifecycle."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    processes: list[subprocess.Popen[bytes]] = []

    def _shutdown(signum: int | None = None, frame: FrameType | None = None) -> None:
        logger.info("Shutting down...")
        for proc in reversed(processes):
            proc.terminate()
        for proc in reversed(processes):
            proc.wait(timeout=5)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Start MCP servers
    weather_proc = _start_weather_mcp()
    processes.append(weather_proc)

    news_proc = _start_news_mcp()
    processes.append(news_proc)

    # Wait for MCP servers to be ready
    if not _wait_for_server(WEATHER_MCP_PORT, "Weather MCP"):
        _shutdown()
        return
    if not _wait_for_server(NEWS_MCP_PORT, "News MCP"):
        _shutdown()
        return

    # Start Streamlit
    streamlit_proc = _start_streamlit()
    processes.append(streamlit_proc)

    logger.info("All services running. Press Ctrl+C to stop.")

    try:
        streamlit_proc.wait()
    except KeyboardInterrupt:
        _shutdown()


if __name__ == "__main__":
    main()

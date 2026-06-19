"""Worker entrypoint.

M0: a stub that stays alive so the compose topology is complete. M2 replaces the loop
body with durable queue consumption (claim step → run agent → record audit → advance run).
"""

from __future__ import annotations

import anyio

from captureos.logging import configure_logging, get_logger


async def run() -> None:
    configure_logging()
    logger = get_logger("worker")
    logger.info("worker.start", note="M0 stub — durable queue consumption arrives in M2")
    while True:  # noqa: ASYNC110 - idle stub loop; replaced by queue consumption in M2
        await anyio.sleep(5)  # pragma: no cover


def main() -> None:
    anyio.run(run)


if __name__ == "__main__":
    main()

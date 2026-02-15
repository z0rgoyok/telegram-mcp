from __future__ import annotations

import logging

from .presentation.server import create_server


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()

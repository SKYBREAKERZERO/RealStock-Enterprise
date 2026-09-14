from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from libs.database import get_engine  # noqa: E402
from libs.database.models import Base  # noqa: E402


def main() -> int:
    engine = get_engine()

    print("Creating RealStock database schema...")

    Base.metadata.create_all(
        bind=engine,
    )

    print("Database schema READY")

    print(
        "Tables:",
        ", ".join(
            sorted(
                Base.metadata.tables.keys()
            )
        ),
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
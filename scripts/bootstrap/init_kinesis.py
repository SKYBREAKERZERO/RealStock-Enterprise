from __future__ import annotations

import sys
from pathlib import Path

from botocore.exceptions import ClientError

ROOT_DIR = Path(__file__).resolve().parents[2]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from libs.aws import get_kinesis_client  # noqa: E402

STREAM_NAME = "realstock-market-events-local"


def main() -> int:
    client = get_kinesis_client()

    try:
        response = client.describe_stream_summary(
            StreamName=STREAM_NAME,
        )

        status = response[
            "StreamDescriptionSummary"
        ]["StreamStatus"]

        print(
            f"Kinesis stream already exists: "
            f"{STREAM_NAME} ({status})"
        )

    except ClientError as exc:
        error_code = (
            exc.response
            .get("Error", {})
            .get("Code")
        )

        if error_code != "ResourceNotFoundException":
            raise

        print(
            f"Creating Kinesis stream: "
            f"{STREAM_NAME}"
        )

        client.create_stream(
            StreamName=STREAM_NAME,
            ShardCount=1,
        )

    waiter = client.get_waiter(
        "stream_exists"
    )

    waiter.wait(
        StreamName=STREAM_NAME,
    )

    response = client.describe_stream_summary(
        StreamName=STREAM_NAME,
    )

    summary = response[
        "StreamDescriptionSummary"
    ]

    print(
        "Kinesis stream READY"
    )

    print(
        f"Name   : {summary['StreamName']}"
    )

    print(
        f"Status : {summary['StreamStatus']}"
    )

    print(
        f"Shards : {summary['OpenShardCount']}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
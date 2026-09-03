from __future__ import annotations

from dataclasses import dataclass

from libs.aws import get_kinesis_client
from libs.events import EventEnvelope


DEFAULT_STREAM_NAME = "realstock-market-events-local"


@dataclass(frozen=True)
class PublishResult:
    shard_id: str
    sequence_number: str


class KinesisMarketEventProducer:
    """
    Publishes canonical RealStock events to Amazon Kinesis.

    This class is responsible only for transport.
    It does not create or validate market-domain objects.
    """

    def __init__(
        self,
        *,
        stream_name: str = DEFAULT_STREAM_NAME,
    ) -> None:
        self._stream_name = stream_name
        self._client = get_kinesis_client()

    @property
    def stream_name(self) -> str:
        return self._stream_name

    def publish(
        self,
        event: EventEnvelope,
        *,
        partition_key: str,
    ) -> PublishResult:
        normalized_partition_key = (
            partition_key.strip()
        )

        if not normalized_partition_key:
            raise ValueError(
                "partition_key must not be empty"
            )

        encoded_partition_key = (
            normalized_partition_key.encode("utf-8")
        )

        if len(encoded_partition_key) > 256:
            raise ValueError(
                "partition_key must not exceed 256 bytes"
            )

        payload = (
            event.to_event_json()
            .encode("utf-8")
        )

        response = self._client.put_record(
            StreamName=self._stream_name,
            Data=payload,
            PartitionKey=normalized_partition_key,
        )

        return PublishResult(
            shard_id=response["ShardId"],
            sequence_number=response[
                "SequenceNumber"
            ],
        )
"""Redis Streams abstraction for task distribution."""

from __future__ import annotations

import redis.asyncio as redis
from pydantic import BaseModel

TASK_STREAM = "llmfuzz:tasks"
RESULT_STREAM = "llmfuzz:results"
WORKER_GROUP = "fuzz-workers"
COORDINATOR_GROUP = "coordinator"


class RedisStreamProducer:
    def __init__(self, client: redis.Redis, stream_name: str):
        self.client = client
        self.stream = stream_name

    async def publish(self, message: BaseModel) -> str:
        """Publish a Pydantic model as a Redis Stream message. Returns message ID."""
        data = {"payload": message.model_dump_json()}
        msg_id = await self.client.xadd(self.stream, data)
        return msg_id


class RedisStreamConsumer:
    def __init__(
        self,
        client: redis.Redis,
        stream_name: str,
        group_name: str,
        consumer_name: str,
    ):
        self.client = client
        self.stream = stream_name
        self.group = group_name
        self.consumer = consumer_name

    async def ensure_group(self) -> None:
        """Create the consumer group if it doesn't exist."""
        try:
            await self.client.xgroup_create(
                self.stream, self.group, id="0", mkstream=True
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def read(
        self, count: int = 1, block_ms: int = 5000
    ) -> list[tuple[str, bytes]]:
        """Read new messages. Returns list of (msg_id, payload_bytes)."""
        messages = await self.client.xreadgroup(
            self.group,
            self.consumer,
            {self.stream: ">"},
            count=count,
            block=block_ms,
        )
        results: list[tuple[str, bytes]] = []
        for _stream_name, msg_list in messages:
            for msg_id, fields in msg_list:
                results.append((msg_id, fields[b"payload"]))
        return results

    async def ack(self, msg_id: str) -> None:
        """Acknowledge a processed message."""
        await self.client.xack(self.stream, self.group, msg_id)

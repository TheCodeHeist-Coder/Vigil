"""Thin helpers over confluent-kafka so services stay short."""

import json
import time
from collections.abc import Iterator

from confluent_kafka import OFFSET_END, Consumer, Producer, TopicPartition
from pydantic import BaseModel

from common.config import settings


def stamp(times: dict[str, float], name: str) -> dict[str, float]:
    """Adds one hop time, so the screen can show the delay per service."""
    return {**times, f"t_{name}": time.time()}


def producer(**overrides: str | int) -> Producer:
    return Producer(
        {
            "bootstrap.servers": settings.kafka_bootstrap,
            "linger.ms": 0,
            "acks": 1,
            "message.max.bytes": 2_097_152,
            **overrides,
        }
    )


def consumer(group: str, topics: list[str], from_start: bool = False) -> Consumer:
    c = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap,
            "group.id": group,
            "auto.offset.reset": "earliest" if from_start else "latest",
            "enable.auto.commit": True,
            "fetch.message.max.bytes": 2_097_152,
        }
    )
    c.subscribe(topics)
    return c


def latest_only_consumer(topic: str, partition: int = 0) -> Consumer:
    """Starts at the end of a topic with no group state, for live views."""
    c = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap,
            "group.id": f"live-{topic}-{time.time_ns()}",
            "enable.auto.commit": False,
            "fetch.message.max.bytes": 2_097_152,
        }
    )
    c.assign([TopicPartition(topic, partition, OFFSET_END)])
    return c


def publish(p: Producer, topic: str, message: BaseModel, key: str) -> None:
    p.produce(topic, value=message.model_dump_json().encode(), key=key)
    p.poll(0)


def messages(c: Consumer, timeout: float = 0.2) -> Iterator[tuple[str, dict]]:
    """Yields (topic, json body) forever, skipping broker errors."""
    while True:
        msg = c.poll(timeout)
        if msg is None:
            continue
        if msg.error():
            print(f"kafka: {msg.error()}", flush=True)
            continue
        yield msg.topic(), json.loads(msg.value())

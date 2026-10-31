"""Creates every Kafka topic. Safe to run again."""

from confluent_kafka.admin import AdminClient, NewTopic

from common.config import settings
from contracts.topics import TOPIC_CONFIG


def main() -> None:
    admin = AdminClient({"bootstrap.servers": settings.kafka_bootstrap})
    existing = admin.list_topics(timeout=10).topics
    wanted = [
        NewTopic(name, num_partitions=1, replication_factor=1, config=config)
        for name, config in TOPIC_CONFIG.items()
        if name not in existing
    ]
    for name, future in admin.create_topics(wanted).items() if wanted else []:
        future.result()
        print(f"created {name}")
    print(f"{len(TOPIC_CONFIG)} topics ready")


if __name__ == "__main__":
    main()

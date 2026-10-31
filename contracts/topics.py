"""Every Kafka topic in the system, in one place."""

FRAMES_RAW = "frames.raw"
HAND_TRACKS = "hand.tracks"
BENCH_EVENTS = "bench.events"
ALERTS_REFLEX = "alerts.reflex"
FLAGS = "flags"
VERDICTS = "verdicts"
INCIDENTS = "incidents"
RUN_CONTROL = "run.control"

MINUTE_MS = 60_000
GIGABYTE = 1024**3

# Each bench owns a key, so one partition per bench keeps its events in order.
TOPIC_CONFIG: dict[str, dict[str, str]] = {
    FRAMES_RAW: {
        "retention.ms": str(15 * MINUTE_MS),
        "retention.bytes": str(GIGABYTE),
        "segment.bytes": str(100 * 1024**2),
    },
    HAND_TRACKS: {"retention.ms": str(60 * MINUTE_MS)},
    BENCH_EVENTS: {"retention.ms": str(7 * 24 * 60 * MINUTE_MS)},
    ALERTS_REFLEX: {"retention.ms": str(7 * 24 * 60 * MINUTE_MS)},
    FLAGS: {"retention.ms": str(7 * 24 * 60 * MINUTE_MS)},
    VERDICTS: {"retention.ms": str(7 * 24 * 60 * MINUTE_MS)},
    INCIDENTS: {"retention.ms": str(7 * 24 * 60 * MINUTE_MS)},
    RUN_CONTROL: {"retention.ms": str(7 * 24 * 60 * MINUTE_MS)},
}

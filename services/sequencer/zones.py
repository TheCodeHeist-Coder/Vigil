"""Turns hand positions into bench events: pick, place and hands_clear."""

from dataclasses import dataclass, field

from contracts.models import Point, Zone

DWELL_SECONDS = 0.2
CLEAR_SECONDS = 0.7
GRACE_SECONDS = 0.25  # one missed detection must not reset a dwell


def inside(point: Point, polygon: list[Point]) -> bool:
    x, y = point
    hit = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


@dataclass
class ZoneTracker:
    zones: list[Zone]
    entered: dict[str, float] = field(default_factory=dict)
    last_seen: dict[str, float] = field(default_factory=dict)
    fired: set[str] = field(default_factory=set)
    carrying: bool = False
    placed: bool = False
    tray_left_at: float | None = None

    def update(self, hands: list[Point], now: float) -> list[tuple[str, str]]:
        events: list[tuple[str, str]] = []
        for zone in self.zones:
            present = any(inside(hand, zone.polygon) for hand in hands)
            if present:
                self.last_seen[zone.id] = now
            elif now - self.last_seen.get(zone.id, -1e9) > GRACE_SECONDS:
                self.entered.pop(zone.id, None)
                self.fired.discard(zone.id)
                continue
            if not present:
                continue  # grace keeps a dwell alive, but a hand that left must never fire it
            self.entered.setdefault(zone.id, now)
            if zone.id in self.fired or now - self.entered[zone.id] < DWELL_SECONDS:
                continue
            if zone.kind == "bin":
                self.fired.add(zone.id)
                self.carrying = True
                self.placed = False
                events.append(("pick", zone.id))
            elif self.carrying:
                self.fired.add(zone.id)
                self.carrying = False
                self.placed = True
                self.tray_left_at = None
                events.append(("place", zone.id))

        tray = next((z for z in self.zones if z.kind == "tray"), None)
        if tray and self.placed:
            if any(inside(hand, tray.polygon) for hand in hands):
                self.tray_left_at = None
            elif self.tray_left_at is None:
                self.tray_left_at = now
            elif now - self.tray_left_at >= CLEAR_SECONDS:
                self.placed = False
                self.tray_left_at = None
                events.append(("hands_clear", tray.id))
        return events

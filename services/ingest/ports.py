"""Keeps WebRTC on a fixed UDP port range, so a server firewall can stay narrow.

The ICE library binds to port 0, which means any port. This picks one from the range instead.
"""

import asyncio
from collections.abc import Callable
from itertools import cycle


def parse_range(text: str) -> range:
    first, last = text.split("-")
    return range(int(first), int(last) + 1)


def limit_udp_ports(loop: asyncio.AbstractEventLoop, ports: range) -> None:
    bind = loop.create_datagram_endpoint
    order = cycle(ports)

    async def bind_in_range(factory: Callable, local_addr=None, **kwargs):
        if local_addr is None or local_addr[1] != 0:
            return await bind(factory, local_addr=local_addr, **kwargs)
        for _ in ports:
            try:
                return await bind(factory, local_addr=(local_addr[0], next(order)), **kwargs)
            except OSError:
                continue
        raise OSError(f"no free UDP port in {ports.start}-{ports.stop - 1}")

    loop.create_datagram_endpoint = bind_in_range

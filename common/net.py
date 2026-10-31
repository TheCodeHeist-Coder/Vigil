"""Tries IPv4 before IPv6.

Python tries addresses one at a time. On a network with broken IPv6, Google's eight IPv6
addresses each hang until timeout before IPv4 is ever tried, so every Gemini call fails.
"""

import socket

_getaddrinfo = socket.getaddrinfo


def _ipv4_first(*args, **kwargs):
    return sorted(_getaddrinfo(*args, **kwargs), key=lambda info: info[0] != socket.AF_INET)


socket.getaddrinfo = _ipv4_first

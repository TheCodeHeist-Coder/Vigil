import socket

import common.net  # noqa: F401


def test_ipv4_is_tried_before_ipv6():
    infos = socket.getaddrinfo("localhost", 443, type=socket.SOCK_STREAM)
    families = [info[0] for info in infos]
    if socket.AF_INET in families and socket.AF_INET6 in families:
        assert families.index(socket.AF_INET) < families.index(socket.AF_INET6)

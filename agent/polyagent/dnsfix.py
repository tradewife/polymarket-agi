"""Pin Polymarket hostnames to Cloudflare IPs.

This machine's resolver returns a certificate that does not match
gamma-api.polymarket.com. Connecting by hostname after rewriting A records
keeps TLS valid.
"""

from __future__ import annotations

import socket

POLYMARKET_IPS: dict[str, str] = {
    "gamma-api.polymarket.com": "104.18.34.205",
    "clob.polymarket.com": "104.18.34.205",
    "data-api.polymarket.com": "104.18.34.205",
    "relayer-v2.polymarket.com": "104.18.34.205",
    "ws-subscriptions-clob.polymarket.com": "104.18.34.205",
}

_original_getaddrinfo = socket.getaddrinfo
_installed = False


def install() -> None:
    global _installed
    if _installed:
        return

    def patched(host, port, family=0, type=0, proto=0, flags=0):
        if isinstance(host, str) and host in POLYMARKET_IPS:
            host = POLYMARKET_IPS[host]
        return _original_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = patched  # type: ignore[assignment]
    _installed = True

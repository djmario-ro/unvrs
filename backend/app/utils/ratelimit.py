import ipaddress
import time
from collections import defaultdict, deque
from functools import lru_cache

from fastapi import HTTPException, Request, status

from app.config import settings

# In-memory sliding-window counters. Suitable for a single backend instance
# (this deployment). For multi-worker/multi-instance, back this with Redis.
_windows: dict[str, deque[float]] = defaultdict(deque)

_Network = ipaddress.IPv4Network | ipaddress.IPv6Network

# Named groups usable in TRUSTED_PROXIES.
_PRIVATE = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
]
# https://www.cloudflare.com/ips/ — stable for years; refresh if Cloudflare
# announces a change.
_CLOUDFLARE = [
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
]
_GROUPS = {"private": _PRIVATE, "cloudflare": _CLOUDFLARE}


@lru_cache(maxsize=1)
def _trusted_networks() -> list[_Network]:
    nets: list[_Network] = []
    for item in settings.trusted_proxies.split(","):
        item = item.strip().lower()
        if not item:
            continue
        for cidr in _GROUPS.get(item, [item]):
            nets.append(ipaddress.ip_network(cidr, strict=False))
    return nets


@lru_cache(maxsize=1)
def _cloudflare_networks() -> list[_Network]:
    return [ipaddress.ip_network(c) for c in _CLOUDFLARE]


def _in(raw: str, nets: list[_Network]) -> bool:
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return False
    return any(addr in net for net in nets)


def _is_trusted(raw: str) -> bool:
    return _in(raw, _trusted_networks())


def client_ip(request: Request) -> str:
    """Client IP as seen by the outermost *trusted* proxy.

    Every proxy appends its caller's address to X-Forwarded-For, so the
    header reads ``client-supplied..., client, proxy1, proxy2``. Walking from
    the right and skipping addresses that belong to our own proxies (private
    networks, Cloudflare) lands on the real client; anything the client
    forged sits further left and is never reached.

    A proxy in the chain may drop the incoming header instead of appending
    (Coolify's Traefik does), leaving only ``cloudflare-edge, traefik``. When
    the chain ends at Cloudflare like that, Cloudflare's own
    ``CF-Connecting-IP`` is the client: it only reaches us through Cloudflare,
    since a request that bypasses Cloudflare shows its real source in the
    chain and never gets here. Values are capped so they are safe to use as
    rate-limit keys.
    """
    peer = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for", "")
    parts = [p.strip() for p in forwarded.split(",") if p.strip()]
    if not parts:
        return peer
    for candidate in reversed(parts):
        if not _is_trusted(candidate):
            return candidate[:64]
    # Everything in the chain is ours.
    if "cloudflare" in settings.trusted_proxies.lower() and any(
        _in(p, _cloudflare_networks()) for p in parts
    ):
        cf_ip = request.headers.get("cf-connecting-ip", "").strip()
        if cf_ip:
            return cf_ip[:64]
    # Internal caller: the left-most entry is the closest thing to an origin.
    return parts[0][:64]


# Drop windows that have fully expired, so a scanner hitting many distinct
# rooms or usernames can't grow the dict without bound.
_PRUNE_EVERY = 500
# Longest window any caller uses; anything older than this can never matter.
_MAX_WINDOW = 300.0
_calls_since_prune = 0


def _prune(now: float) -> None:
    cutoff = now - _MAX_WINDOW
    stale = [k for k, bucket in _windows.items() if not bucket or bucket[-1] <= cutoff]
    for k in stale:
        del _windows[k]


def enforce(key: str, max_attempts: int, window_seconds: float) -> None:
    """Record an attempt for ``key`` and raise 429 if the window is exceeded."""
    global _calls_since_prune
    now = time.monotonic()
    _calls_since_prune += 1
    if _calls_since_prune >= _PRUNE_EVERY:
        _calls_since_prune = 0
        _prune(now)
    bucket = _windows[key]
    cutoff = now - window_seconds
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()
    if len(bucket) >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
            headers={"Retry-After": str(int(window_seconds))},
        )
    bucket.append(now)

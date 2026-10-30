import pytest

from app.utils.ratelimit import client_ip


class FakeRequest:
    def __init__(self, xff: str | None, peer: str = "10.0.0.9", cf_ip: str | None = None):
        self.headers = {"x-forwarded-for": xff} if xff is not None else {}
        if cf_ip is not None:
            self.headers["cf-connecting-ip"] = cf_ip
        self.client = type("Client", (), {"host": peer})()


def test_chain_ending_at_cloudflare_uses_cf_connecting_ip():
    # Coolify's Traefik drops the incoming header and appends only its caller
    # (the Cloudflare edge); nginx then appends Traefik. Production looks like this.
    r = FakeRequest("162.158.10.20, 172.29.0.6", cf_ip="198.51.100.7")
    assert client_ip(r) == "198.51.100.7"


def test_cf_connecting_ip_ignored_when_request_bypassed_cloudflare():
    # Hitting Traefik directly: the real source is in the chain and wins.
    r = FakeRequest("203.0.113.5, 172.29.0.6", cf_ip="198.51.100.7")
    assert client_ip(r) == "203.0.113.5"


def test_cf_connecting_ip_ignored_without_cloudflare_in_chain():
    r = FakeRequest("10.0.0.3, 172.29.0.6", cf_ip="198.51.100.7")
    assert client_ip(r) == "10.0.0.3"


@pytest.mark.parametrize(
    "xff, expected",
    [
        # Cloudflare → Traefik → nginx
        ("198.51.100.7, 188.114.96.8, 10.0.0.1", "198.51.100.7"),
        # forged entries on the left are never reached
        ("1.1.1.1, 2.2.2.2, 198.51.100.7, 188.114.96.8, 10.0.0.1", "198.51.100.7"),
        # nginx only (local compose)
        ("198.51.100.7, 172.18.0.5", "198.51.100.7"),
        ("9.9.9.9, 198.51.100.7, 172.18.0.5", "198.51.100.7"),
        # everything internal: left-most is the origin
        ("10.0.0.3, 10.0.0.1", "10.0.0.3"),
        # garbage is untrusted, hence treated as the client (and bounded)
        ("not-an-ip, 10.0.0.1", "not-an-ip"),
        ("x" * 500 + ", 10.0.0.1", "x" * 64),
        # IPv6 behind Cloudflare
        ("2001:db8::1, 2606:4700::1, 10.0.0.1", "2001:db8::1"),
    ],
)
def test_client_ip_walks_past_trusted_proxies(xff, expected):
    assert client_ip(FakeRequest(xff)) == expected


def test_client_ip_without_header_is_peer():
    assert client_ip(FakeRequest(None, peer="203.0.113.5")) == "203.0.113.5"


def test_expired_windows_are_pruned():
    """A scanner hitting many distinct keys must not grow the dict forever."""
    import time as _time

    from app.utils import ratelimit

    ratelimit._windows.clear()
    ratelimit._calls_since_prune = 0
    # Fill with keys whose entries are already far outside any window.
    old = _time.monotonic() - (ratelimit._MAX_WINDOW + 60)
    for i in range(ratelimit._PRUNE_EVERY):
        ratelimit._windows[f"stale:{i}"].append(old)
    assert len(ratelimit._windows) == ratelimit._PRUNE_EVERY
    # One more call crosses the prune threshold.
    for i in range(ratelimit._PRUNE_EVERY):
        ratelimit.enforce("live", max_attempts=10_000, window_seconds=60)
    assert len(ratelimit._windows) == 1  # only the live key survives
    ratelimit._windows.clear()

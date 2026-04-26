"""Shared HTTP utilities for the scraping subsystem — Phase 2.

Centralizes:
  • User-Agent rotation so every outbound request looks like a real browser
    and we are not trivially fingerprintable by a single static UA.
  • A `retry_with_backoff` helper for transient HTTP failures (5xx + the
    `httpx` connection/read-timeout family). 4xx responses are NOT retried —
    those are deliberate refusals from the upstream and re-trying them just
    makes us more bannable.
  • A `NominatimRateLimiter` token-bucket so concurrent geocodes cannot
    violate the 1 req/s policy regardless of how many enrichment workers
    are firing.

Used by:
  • services/scraper_service.py (HomeHarvest call wrap)
  • services/image_service.py (per-image download retry)
  • services/enrichment_service.py (geocode rate-limit)
  • services/scrapers/*.py (random UA per request)
"""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import Callable, Optional, TypeVar

import httpx

logger = logging.getLogger(__name__)


# ── User-Agent pool ──────────────────────────────────────────────────────────
# Modern desktop UAs from real Chrome / Firefox / Safari builds. Rotated per
# request. Keep this list small — too many UAs from the same IP looks worse
# than one consistent UA. 5 is a good balance.
USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
)

_DEFAULT_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,*/*;q=0.8"
)


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def random_headers(extra: Optional[dict] = None) -> dict:
    """Return a fresh header dict with a rotated UA + sensible defaults.
    Pass `extra` to override or add fields per call (e.g. Referer)."""
    headers = {
        "User-Agent": random_user_agent(),
        "Accept": _DEFAULT_ACCEPT,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }
    if extra:
        headers.update(extra)
    return headers


# ── Retry with exponential backoff ───────────────────────────────────────────
# Only retry transport-level failures and 5xx responses. NEVER retry 4xx —
# the upstream told us no on purpose, and hammering it makes things worse.

T = TypeVar("T")

_TRANSIENT_HTTPX_EXC = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    label: str = "request",
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> T:
    """Run `fn` up to `attempts` times with exponential backoff between tries.

    Retries on:
      • httpx transport errors (connect/read/write/pool timeouts, protocol)
      • httpx.HTTPStatusError where status >= 500

    Re-raises immediately on:
      • httpx.HTTPStatusError where status < 500 (4xx is intentional)
      • Any other exception type

    `on_retry(attempt, exc)` is called after each failed attempt that will
    be retried — useful for recording metrics.errors entries at the caller.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except _TRANSIENT_HTTPX_EXC as exc:
            last_exc = exc
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code < 500:
                raise
            last_exc = exc
        except Exception:
            raise

        if attempt >= attempts:
            break

        if on_retry is not None:
            try:
                on_retry(attempt, last_exc)
            except Exception:
                pass

        delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
        logger.info(
            "retry_with_backoff[%s]: attempt %d/%d failed (%s) — sleeping %.1fs",
            label, attempt, attempts, type(last_exc).__name__, delay,
        )
        time.sleep(delay)

    assert last_exc is not None
    raise last_exc


# ── Nominatim token bucket ───────────────────────────────────────────────────
# OSM Nominatim TOS: max 1 request per second per app, with a real UA + email.
# This rate-limiter is process-global and thread-safe, so any concurrent
# enrichment task that touches geocode_property() will queue behind any
# other in-flight Nominatim call.

class _RateLimiter:
    """Simple token-bucket-style rate limiter. Blocks `acquire()` until at
    least `min_interval` seconds have passed since the last successful call."""

    def __init__(self, min_interval: float):
        self._min_interval = min_interval
        self._lock = threading.Lock()
        self._last_call: float = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()


nominatim_limiter = _RateLimiter(min_interval=1.05)

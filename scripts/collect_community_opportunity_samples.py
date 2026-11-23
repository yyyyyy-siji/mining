"""Backward-compatible CLI wrapper for the packaged community sampler.

Original import paths and CLI flags remain available; application routes import
signal_miner.connectors.community_samples directly.
"""

import sys

from signal_miner.connectors.community_samples import (  # noqa: F401 — public compatibility exports
    API_URL,
    ATOM,
    MAX_LIMIT,
    MAX_REQUESTS,
    PAGE_SIZE,
    V2EX_FEEDS,
    CollectionError,
    CollectionSummary,
    clean_html,
    collect_samples,
    collect_v2ex_samples,
    httpx,
    main,
    normalize_hit,
)

if __name__ == "__main__":
    sys.exit(main())

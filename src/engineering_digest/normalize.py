"""The values stored for each feed entry: its cleaned URL, its article id and its time in UTC."""

import hashlib
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import feedparser


def clean_url(url: str) -> str:
    """Return `url` without its `utm_*` tracking parameters; every other part is kept as it is."""
    parts = urlsplit(url)
    kept: list[str] = [
        parameter
        for parameter in parts.query.split("&")
        if not parameter.lower().startswith("utm_")
    ]
    return urlunsplit(parts._replace(query="&".join(kept)))


def article_id(url: str) -> str:
    """The id of the article at `url`: the SHA-256 hex digest of its cleaned URL."""
    return hashlib.sha256(clean_url(url).encode("utf-8")).hexdigest()


def published_at(entry: feedparser.FeedParserDict) -> datetime | None:
    """When `entry` was published, or else last updated, in UTC; None if the feed gives neither."""
    # feedparser has already converted these to UTC.
    parsed: time.struct_time | None = entry.get("published_parsed") or entry.get(
        "updated_parsed"
    )
    return datetime(*parsed[:6], tzinfo=UTC) if parsed else None

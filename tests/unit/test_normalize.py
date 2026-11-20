from datetime import UTC, datetime

import feedparser

from engineering_digest.normalize import article_id, clean_url, published_at


def atom_entry(dates: str) -> feedparser.FeedParserDict:
    """The single entry of an Atom feed whose entry holds `dates`."""
    feed = feedparser.parse(
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        f"<entry><title>Example</title>{dates}</entry></feed>"
    )
    return feed.entries[0]


def test_tracking_parameters_do_not_change_the_article_id() -> None:
    url = "https://www.example.com/news/2026/11/story/"

    assert article_id(f"{url}?utm_source=feed&utm_medium=rss") == article_id(url)


def test_parameters_that_identify_the_article_are_kept() -> None:
    url = "https://example.com/item?id=123&utm_medium=feed"

    assert clean_url(url) == "https://example.com/item?id=123"


def test_publication_time_is_stored_in_utc() -> None:
    entry = atom_entry("<published>2026-10-29T12:00:00+02:00</published>")

    assert published_at(entry) == datetime(2026, 10, 29, 10, 0, tzinfo=UTC)


def test_entries_with_only_an_updated_time_use_it() -> None:
    # Like GitHub's release feeds.
    entry = atom_entry("<updated>2026-10-29T12:00:00Z</updated>")

    assert published_at(entry) == datetime(2026, 10, 29, 12, 0, tzinfo=UTC)

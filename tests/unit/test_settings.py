import shutil
from pathlib import Path

import pytest

from engineering_digest.settings import PROJECT_ROOT, ConfigError, load_settings


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A project root holding copies of the committed sources.yaml and preferences.yaml."""
    (tmp_path / "config").mkdir()
    for name in ("sources.yaml", "preferences.yaml"):
        shutil.copy(PROJECT_ROOT / "config" / name, tmp_path / "config" / name)
    return tmp_path


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def source_entry(source_id: str, name: str, kind: str = "primary") -> str:
    return (
        f"  - id: {source_id}\n"
        f"    name: {name}\n"
        f"    url: https://example.com/{source_id}.xml\n"
        f"    kind: {kind}\n"
        f"    credibility: 3\n"
    )


def test_committed_config_loads_and_unedited_example_files_change_nothing(
    root: Path,
) -> None:
    committed = load_settings(root)
    shutil.copy(PROJECT_ROOT / "config/local.example.yaml", root / "config/local.yaml")
    shutil.copy(PROJECT_ROOT / ".env.example", root / ".env")

    settings = load_settings(root)

    assert settings == committed
    assert settings.anthropic_api_key is None


def test_api_key_is_read_from_env_file(root: Path) -> None:
    write(root / ".env", "ANTHROPIC_API_KEY=test-value\n")

    key = load_settings(root).anthropic_api_key

    assert key is not None and key.get_secret_value() == "test-value"


def test_unknown_source_kind_names_the_source(root: Path) -> None:
    write(
        root / "config/sources.yaml",
        "sources:\n" + source_entry("example", "Example Feed", kind="blog"),
    )

    with pytest.raises(ConfigError, match="source 'Example Feed': kind: "):
        load_settings(root)


def test_unknown_source_topic_names_the_source(root: Path) -> None:
    write(
        root / "config/sources.yaml",
        "sources:\n"
        + source_entry("example", "Example Feed")
        + "    topics: [ai-codng]\n",
    )

    with pytest.raises(ConfigError, match="'Example Feed' lists topics .*: ai-codng"):
        load_settings(root)


def test_duplicate_source_ids_are_rejected(root: Path) -> None:
    write(
        root / "config/sources.yaml",
        "sources:\n"
        + source_entry("example", "First")
        + source_entry("example", "Second"),
    )

    with pytest.raises(ConfigError, match="'First' and 'Second' have the same id"):
        load_settings(root)


def test_local_sources_change_listed_fields_and_add_new_sources(root: Path) -> None:
    write(
        root / "config/sources.yaml",
        "sources:\n"
        + source_entry("first", "First")
        + source_entry("second", "Second"),
    )
    committed = {source.id: source for source in load_settings(root).sources}
    write(
        root / "config/local.yaml",
        "sources:\n  - id: first\n    enabled: false\n"
        + source_entry("added", "Added"),
    )

    sources = {source.id: source for source in load_settings(root).sources}

    assert sources.pop("first") == committed.pop("first").model_copy(
        update={"enabled": False}
    )
    assert sources.pop("added").name == "Added"
    assert sources == committed


def test_local_preferences_merge_into_committed_topics(root: Path) -> None:
    committed = dict(load_settings(root).preferences.topics)
    write(
        root / "config/local.yaml",
        "preferences:\n  topics:\n    your-stack:\n      keywords: [Rust]\n",
    )

    topics = dict(load_settings(root).preferences.topics)

    assert topics.pop("your-stack") == committed.pop("your-stack").model_copy(
        update={"keywords": ("Rust",)}
    )
    assert topics == committed

"""Settings from the committed config, the optional config/local.yaml and .env."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
SOURCES_FILE = Path("config/sources.yaml")
PREFERENCES_FILE = Path("config/preferences.yaml")
LOCAL_FILE = Path("config/local.yaml")
ENV_FILE = Path(".env")

type YamlMapping = dict[str, Any]


class ConfigError(Exception):
    """A config file is invalid; the message names the file and the record at fault."""


class _ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(_ConfigModel):
    """One feed; config/sources.yaml describes the fields."""

    id: str
    name: str
    url: HttpUrl
    kind: Literal["primary", "commentary", "aggregator"]
    credibility: int = Field(ge=1, le=5)
    rollup: bool = False
    topics: tuple[str, ...] = ()
    enabled: bool = True


class Topic(_ConfigModel):
    label: str
    keywords: tuple[str, ...]


class Preferences(_ConfigModel):
    """The contents of config/preferences.yaml."""

    digest_interval_days: int = Field(ge=1)
    relevance_question: str
    topics: dict[str, Topic]
    exclude_keywords: tuple[str, ...]
    skip_prerelease_versions: bool


class _SourcesFile(_ConfigModel):
    sources: list[YamlMapping]


class _LocalFile(_ConfigModel):
    sources: list[YamlMapping] = []
    preferences: YamlMapping = {}


class _Secrets(BaseSettings):
    # An empty value, as in .env.example, counts as unset.
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8", env_ignore_empty=True, extra="ignore"
    )

    anthropic_api_key: SecretStr | None = None


@dataclass(frozen=True)
class Settings:
    sources: tuple[Source, ...]
    preferences: Preferences
    anthropic_api_key: SecretStr | None


def load_settings(root: Path = PROJECT_ROOT) -> Settings:
    """Load the config under `root`; raises ConfigError if any of it is invalid."""
    sources_file = _validate(
        _SourcesFile, _read_yaml(root / SOURCES_FILE), SOURCES_FILE
    )
    preferences = _validate(
        Preferences, _read_yaml(root / PREFERENCES_FILE), PREFERENCES_FILE
    )
    local = _LocalFile()
    if (root / LOCAL_FILE).exists():
        # An empty or all-comments file loads as None.
        local = _validate(_LocalFile, _read_yaml(root / LOCAL_FILE) or {}, LOCAL_FILE)

    sources = _merge_sources(sources_file.sources, local.sources)
    if local.preferences:
        merged = _merge(preferences.model_dump(mode="json"), local.preferences)
        preferences = _validate(Preferences, merged, LOCAL_FILE)

    for source in sources:
        unknown = [topic for topic in source.topics if topic not in preferences.topics]
        if unknown:
            raise ConfigError(
                f"Source {source.name!r} lists topics that aren't in "
                f"{PREFERENCES_FILE.as_posix()}: {', '.join(unknown)}"
            )

    secrets = _Secrets(_env_file=root / ENV_FILE)
    return Settings(sources, preferences, secrets.anthropic_api_key)


def _merge_sources(
    committed: list[YamlMapping], overrides: list[YamlMapping]
) -> tuple[Source, ...]:
    """Apply config/local.yaml's source entries, matched by id, to the committed ones."""
    by_id: dict[str, Source] = {}
    for entry in committed:
        source = _validate(Source, entry, SOURCES_FILE, _source_label(entry))
        if source.id in by_id:
            raise ConfigError(
                f"{SOURCES_FILE.as_posix()}: sources {by_id[source.id].name!r} and "
                f"{source.name!r} have the same id, {source.id!r}"
            )
        by_id[source.id] = source

    for entry in overrides:
        source_id = entry.get("id")
        if not isinstance(source_id, str):
            raise ConfigError(
                f"{LOCAL_FILE.as_posix()}: {_source_label(entry)} needs an id"
            )
        base = by_id[source_id].model_dump(mode="json") if source_id in by_id else {}
        merged = base | entry
        by_id[source_id] = _validate(Source, merged, LOCAL_FILE, _source_label(merged))
    return tuple(by_id.values())


def _merge(base: YamlMapping, override: YamlMapping) -> YamlMapping:
    """Merge mappings key by key; any other value in `override` replaces the one in `base`."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _source_label(entry: YamlMapping) -> str:
    label = entry.get("name") or entry.get("id")
    return f"source {label!r}" if label else "a source with no name or id"


def _read_yaml(path: Path) -> Any:
    # Reading from the open file puts its path in any YAML syntax error.
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def _validate[M: BaseModel](
    model: type[M], data: object, file: Path, record: str = ""
) -> M:
    """Validate `data` as `model`; raises ConfigError naming `file`, `record` and each problem."""
    try:
        return model.model_validate(data)
    except ValidationError as error:
        problems = [
            f"{'.'.join(map(str, problem['loc']))}: {problem['msg']}"
            if problem["loc"]
            else problem["msg"]
            for problem in error.errors()
        ]
        where = f"{file.as_posix()}, {record}" if record else file.as_posix()
        raise ConfigError(f"{where}: {'; '.join(problems)}") from error

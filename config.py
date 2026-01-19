import json
import os
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

CONFIG_FILE = "sillydata_config.json"
DEFAULT_IMESSAGE_PATH = "~/Library/Messages/chat.db"


class DataSourceType(Enum):
    IMESSAGE = "imessage"
    DISCORD = "discord"


@dataclass
class DataSource:
    name: str
    path: str
    source_type: DataSourceType

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "type": self.source_type.value
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DataSource":
        return cls(
            name=data["name"],
            path=data["path"],
            source_type=DataSourceType(data["type"])
        )

    def get_expanded_path(self) -> str:
        return os.path.expanduser(self.path)

    def exists(self) -> bool:
        expanded = self.get_expanded_path()
        if self.source_type == DataSourceType.IMESSAGE:
            return os.path.isfile(expanded)
        elif self.source_type == DataSourceType.DISCORD:
            messages_path = os.path.join(expanded, "messages")
            if os.path.isdir(messages_path):
                return True
            return os.path.isdir(expanded) and os.path.exists(os.path.join(expanded, "index.json"))
        return False


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"imessage": [], "discord": []}


def save_config(config: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_imessage_sources() -> list[DataSource]:
    config = load_config()
    sources = []
    for item in config.get("imessage", []):
        sources.append(DataSource.from_dict({**item, "type": "imessage"}))
    return sources


def get_discord_sources() -> list[DataSource]:
    config = load_config()
    sources = []
    for item in config.get("discord", []):
        sources.append(DataSource.from_dict({**item, "type": "discord"}))
    return sources


def add_imessage_source(name: str, path: str) -> DataSource:
    config = load_config()
    source = DataSource(name=name, path=path, source_type=DataSourceType.IMESSAGE)
    config.setdefault("imessage", []).append({"name": name, "path": path})
    save_config(config)
    return source


def add_discord_source(name: str, path: str) -> DataSource:
    config = load_config()
    source = DataSource(name=name, path=path, source_type=DataSourceType.DISCORD)
    config.setdefault("discord", []).append({"name": name, "path": path})
    save_config(config)
    return source


def remove_imessage_source(name: str) -> bool:
    config = load_config()
    original_len = len(config.get("imessage", []))
    config["imessage"] = [s for s in config.get("imessage", []) if s["name"] != name]
    if len(config["imessage"]) < original_len:
        save_config(config)
        return True
    return False


def remove_discord_source(name: str) -> bool:
    config = load_config()
    original_len = len(config.get("discord", []))
    config["discord"] = [s for s in config.get("discord", []) if s["name"] != name]
    if len(config["discord"]) < original_len:
        save_config(config)
        return True
    return False


def get_default_imessage_path() -> str:
    return DEFAULT_IMESSAGE_PATH


def check_default_imessage_exists() -> bool:
    return os.path.isfile(os.path.expanduser(DEFAULT_IMESSAGE_PATH))

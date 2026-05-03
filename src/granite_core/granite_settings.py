from __future__ import annotations

import dataclasses
import json  # 本来按照行业趋向应该用 TOML 的，but tomllib 在 3.11 才被加入，还不熟，就用 JSON 了  # noqa
import logging
import os
import pathlib
import platform

# 其实就是懒（


@dataclasses.dataclass
class GraniteSettings:
    logger: logging.Logger = logging.getLogger("Settings")
    system_name: str = dataclasses.field(
        init=False, default=platform.system().replace("Darwin", "osx").lower()
    )
    system_version: str = dataclasses.field(init=False, default=platform.version())
    system_architecture: str = dataclasses.field(init=False, default=platform.machine())

    azure_client_id: str = "b5f67794-4e46-4538-9969-b0e2c84222ff"
    current_version: str | None = None
    download_source: str = "Mojang"
    working_path: pathlib.Path = dataclasses.field(default_factory=lambda: pathlib.Path.cwd() / ".minecraft")
    max_workers: int = 128
    temp_path: pathlib.Path = dataclasses.field(
        default_factory=lambda: pathlib.Path(os.environ.get("TEMP", pathlib.Path.cwd())) / "Granite" / "temp"
    )
    jvm_argument_head: str = (
        "-XX:+UseG1GC -XX:-UseAdaptiveSizePolicy "
        "-XX:-OmitStackTraceInFastThrow -Dfml.ignoreInvalidMinecraftCertificates=True "
        "-Dfml.ignorePatchDiscrepancies=True -Dlog4j2.formatMsgNoLookups=true"
    )
    is_demo_user: bool = False
    has_custom_resolution: bool = False
    has_quick_plays_support: bool = False
    is_quick_play_singleplayer: bool = False
    is_quick_play_multiplayer: bool = False
    is_quick_play_realms: bool = False
    maximum_heap_size: int = 2048
    initial_heap_size: int = 1024
    auth_player_name: str | None = None
    auth_uuid: str | None = None
    auth_access_token: str | None = None
    user_type: str | None = None
    quick_play_path: pathlib.Path | None = None
    quick_play_singleplayer: str | None = None
    quick_play_multiplayer: str | None = None
    quick_play_realms: str | None = None

    def post_init(self):
        self.working_path.mkdir(parents=True, exist_ok=True)
        self.temp_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls, config_path: pathlib.Path=pathlib.Path("Granite/settings.json")) -> GraniteSettings:
        if config_path.exists():
            try:
                with config_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                instance = cls()
                for key, value in data.items():
                    if hasattr(instance, key):
                        if key in ("working_path", "temp_path", "quick_play_path") and value is not None:
                            value = pathlib.Path(value)
                        setattr(instance, key, value)
                return instance
            except Exception as e:
                cls.logger.error(f"加载配置文件失败：{e}，使用默认配置")
        return cls()

    def save(self, config_path: pathlib.Path=pathlib.Path("Granite/settings.json")) -> None:
        serializable: dict = {
            k: v for k, v in self.__dict__.items()
            if not k.startswith("system_") and v is not None
        }

        for key, value in serializable.items():
            if isinstance(value, pathlib.Path):
                serializable[key] = str(value)

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)

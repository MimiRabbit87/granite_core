import os
import json  # 本来按照行业趋向应该用 TOML 的，but tomllib 在 3.11 才被加入，还不熟，就用 JSON 了
import pathlib

# 其实就是懒（


class GraniteSettings:
    def __init__(self) -> None:
        settings: dict = {}
        if os.path.exists("settings.json"):
            with open("settings.json", "r") as file:
                settings: dict = json.load(file)

        self.current_version: str = getattr(settings, "current_version", None)  # 当前选择的 Minecraft 版本
        self.working_path: pathlib.Path = getattr(settings, "working_path", pathlib.Path.cwd())
        self.max_workers: int = getattr(settings, "max_workers", 128)  # 最大线程数
        self.temp_path: pathlib.Path = getattr(settings, "temp_path",
                                               pathlib.Path(os.environ.get("TEMP", pathlib.Path.cwd())) / "Granite" / "temp")  # 缓存路径

    def set_setting(self, key: str, value: any) -> None:
        setattr(self, key, value)

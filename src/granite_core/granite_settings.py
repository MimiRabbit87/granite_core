from __future__ import annotations
import logging
import os
import json  # 本来按照行业趋向应该用 TOML 的，but tomllib 在 3.11 才被加入，还不熟，就用 JSON 了
import pathlib
import platform

# 其实就是懒（


class GraniteSettings:
    def __init__(self) -> None:
        settings: dict = {}
        if pathlib.Path.exists(pathlib.Path("Granite/settings.json")):
            try:
                with open(pathlib.Path("Granite/settings.json"), "r") as file:
                    settings: dict = json.load(file)
            except Exception as e:
                logging.error(f"[Settings]: {e}")

        self.system_name: str = platform.system().replace("Darwin", "osx").lower()  # 系统名称（小写）
        self.system_version: str = platform.version()
        self.system_architecture: str = platform.machine()
        self.current_version: str = getattr(settings, "current_version", None)  # 当前选择的 Minecraft 版本
        self.working_path: pathlib.Path = getattr(settings, "working_path", pathlib.Path.cwd() / ".minecraft")  # 当前工作 .minecraft 目录
        self.max_workers: int = getattr(settings, "max_workers", 128)  # 最大线程数
        self.temp_path: pathlib.Path = getattr(
            settings, "temp_path",
            pathlib.Path(os.environ.get("TEMP", pathlib.Path.cwd())) / "Granite" / "temp"
        )  # 缓存路径
        self.jvm_argument_head: str = getattr(
            settings, "jvm_argument_head",
            "-XX:+UseG1GC "
            "-XX:-UseAdaptiveSizePolicy "
            "-XX:-OmitStackTraceInFastThrow "
            "-Dfml.ignoreInvalidMinecraftCertificates=True "
            "-Dfml.ignorePatchDiscrepancies=True "
            "-Dlog4j2.formatMsgNoLookups=true"
        )  # JVM 参数头（字符串字面量隐式拼接太好用了你们知道吗）

        self.save()

    def set(self, key: str, value) -> None:
        setattr(self, key, value)
        self.save()

    def save(self) -> None:
        settings: dict = {
            "current_version": self.current_version,
            "working_path": str(self.working_path),
            "max_workers": self.max_workers,
            "temp_path": str(self.temp_path),
            "jvm_argument_head": self.jvm_argument_head,
        }

        if not pathlib.Path.exists(pathlib.Path("Granite")):
            pathlib.Path("Granite").mkdir(parents=True, exist_ok=True)
        with open(pathlib.Path("Granite/settings.json"), "w") as file:
            json.dump(settings, file, indent=2)

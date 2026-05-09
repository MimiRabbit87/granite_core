"""
    Java Management: manages Javas.
    Copyright (C) 2026 MimiRabbit

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from __future__ import annotations

import concurrent.futures
import logging
import pathlib
import os
import subprocess

from granite_core.granite import granite_settings


class JavaManagement:
    def __init__(
            self,
            settings: granite_settings.GraniteSettings,
            thread_pool_: concurrent.futures.ThreadPoolExecutor) -> None:
        self.logger: logging.Logger = logging.getLogger("JavaManagement")
        self.settings: granite_settings.GraniteSettings = settings
        self.thread_pool: concurrent.futures.ThreadPoolExecutor = thread_pool_
        self.java_list: dict[pathlib.Path, tuple[int, str]] = {}

    def search_for_java_from_environment_variable(self) -> list[pathlib.Path]:
        java_path: list[pathlib.Path] = []
        path_dirs: list[str] = os.environ.get("PATH", "").split(os.pathsep)
        pathext: list[str] = os.environ.get("PATHEXT", "").split(os.pathsep)
        suffixes: set[str] = set([""] + pathext)

        for dir_str in path_dirs:
            if not dir_str:
                continue

            dir_path: pathlib.Path = pathlib.Path(dir_str)
            for suffix in suffixes:
                candidate: pathlib.Path = dir_path / f"java{suffix}"
                if candidate.exists():
                    java_path.append(candidate)
                    self.logger.info(f"找到可能的 Java 可执行文件：{candidate}")

        return java_path

    def search_for_java(self) -> None:
        possible_java_path: list[pathlib.Path] = []

        possible_java_path += self.search_for_java_from_environment_variable()

        futures: list[concurrent.futures.Future[None]] = \
            [self.thread_pool.submit(self.is_java_executable, java) for java in possible_java_path]

        for future in futures:
            future.result()

    def is_java_executable(self, java_path: pathlib.Path) -> None:
        instance: subprocess.CompletedProcess = subprocess.run(
            [java_path, "-XshowSettings:properties", "-version"],
            stderr=subprocess.PIPE,
            text=True
        )

        if "java" in instance.stderr:
            details: dict[str, str] = {}
            for line in instance.stderr.splitlines():
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                details[key] = value

            self.java_list[java_path] = self.parse_java_version(details.get("java.version", ""))
            self.logger.info(f"已证实 {java_path} 为 Java 可执行文件，版本：{self.java_list[java_path][0]}")
        else:
            self.logger.info(f"{java_path} 并非 Java 可执行文件")

    def parse_java_version(self, version_str: str) -> tuple[int, str]:
        # "1.8.0_291" 等
        if version_str.startswith("1."):
            parts: list[str] = version_str.split(".")
            if len(parts) >= 2:
                try:
                    major: int = int(parts[1])
                    return major, version_str
                except Exception as e:
                    self.logger.error(f"在解析 Java 版本号时发生异常：{e}")
                    return 0, version_str

        # "17.0.5" "25" 等
        try:
            major: int = int(version_str.split(".")[0])
            return major, version_str
        except Exception as e:
            self.logger.error(f"在解析 Java 版本号时发生异常：{e}")
            return 0, version_str

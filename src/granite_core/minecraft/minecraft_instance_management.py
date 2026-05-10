"""
    Minecraft Instance Management: manages Minecraft instances.
    Copyright (C) 2026 MimiRabbit

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from __future__ import annotations

import logging
import pathlib
import subprocess

import psutil


class MinecraftInstanceManagement:
    def __init__(self) -> None:
        self.logger: logging.Logger = logging.getLogger("MinecraftInstanceManagement")
        self.instance_list: list[subprocess.Popen] = []  # 由 Granite Core 直接启动的 Minecraft 实例 Popen 对象
        self.external_instances_list: list[psutil.Process] = []  # 由外部启动的疑似 Minecraft 实例进程 Process 对象

    def search_for_game_instances(self) -> None:
        self.external_instances_list = []
        for process in psutil.process_iter(["pid", "name", "cmdline"]):
            if "java" not in process.name():
                continue
            if self.is_game_instance(process):
                self.external_instances_list.append(process)

    def is_game_instance(self, process: psutil.Process) -> bool:
        try:
            command_line: list[str] = process.cmdline()
            if not command_line:
                return False

            minecraft_main_classes: list[str] = [
                "net.minecraft.client.main.Main",
                "net.fabricmc.loader.impl.launch.knot.KnotClient",  # noqa
                "net.minecraft.launchwrapper.Launch",  # noqa
                "cpw.mods.modlauncher.Launcher",  # noqa
                "net.minecraftforge.fml.loading.FMLServerLaunchProvider",  # noqa
                "com.mojang.minecraft.Main",
                "com.mojang.rubydung.RubyDung"  # noqa
            ]
            for minecraft_main_class in minecraft_main_classes:
                if minecraft_main_class in command_line:
                    self.logger.info(
                        f"判断进程 PID {process.info['pid']} 为 Minecraft 实例，"
                        f"因为其命令行参数中含有关键字 {minecraft_main_class}"
                    )
                    return True

            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def launch_game(
            self,
            java_path: pathlib.Path,
            launch_argument: str,
            current_working_directory: pathlib.Path
    ) -> subprocess.Popen:
        instance: subprocess.Popen = subprocess.Popen(
            f"{java_path} {launch_argument}",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
            text=True,
            encoding="utf-8",
            cwd=current_working_directory
        )
        self.instance_list.append(instance)

        return instance

    @staticmethod
    def _read_stdout(instance: subprocess.Popen[str]) -> None:
        for line in instance.stdout:
            print(line, end="")

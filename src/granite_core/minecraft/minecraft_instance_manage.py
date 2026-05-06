from __future__ import annotations

import logging
import pathlib
import subprocess

import psutil


class MinecraftInstanceManage:
    def __init__(self) -> None:
        self.logger: logging.Logger = logging.getLogger("MinecraftInstanceManage")
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

    def launch_game(self, java_path: pathlib.Path, launch_argument: str) -> subprocess.Popen:
        instance: subprocess.Popen = subprocess.Popen(
            f"{java_path} {launch_argument}",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=True
        )
        self.instance_list.append(instance)

        return instance

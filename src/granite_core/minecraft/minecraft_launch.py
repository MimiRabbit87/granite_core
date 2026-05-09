"""
    Minecraft Launch: generates launching commandline of Minecraft.
    Copyright (C) 2026 MimiRabbit

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from __future__ import annotations

import concurrent.futures
import datetime
import json
import logging
import os
import pathlib
import re
import shutil
import time
import zipfile

from granite_core.concurrency import task_queue
from granite_core.granite import granite_settings


class MinecraftLaunch:
    def __init__(
            self,
            settings: granite_settings.GraniteSettings,
            thread_pool_: concurrent.futures.ThreadPoolExecutor
    ) -> None:
        self.logger: logging.Logger = logging.getLogger("Launch")
        self.task_queue: task_queue.TaskQueue = task_queue.TaskQueue(3, thread_pool_)

        self.natives_directory: pathlib.Path = (settings.working_path / "versions" / settings.current_version /
                                                f"{settings.current_version}-natives")
        self.launcher_name: str = "Granite"
        self.launcher_version: str = "114514"
        self.classpath: str = ""

        self.temp_path: pathlib.Path = settings.temp_path
        self.system_name: str = settings.system_name
        self.system_version: str = settings.system_version
        self.system_architecture: str = settings.system_architecture
        self.working_path: pathlib.Path = settings.working_path
        self.version: str = settings.current_version
        self.jvm_argument_head: str = settings.jvm_argument_head
        self.is_demo_user: bool = settings.is_demo_user
        self.has_custom_resolution: bool = settings.has_custom_resolution
        self.has_quick_plays_support: bool = settings.has_quick_plays_support
        self.is_quick_play_singleplayer: bool = settings.is_quick_play_singleplayer
        self.is_quick_play_multiplayer: bool = settings.is_quick_play_multiplayer
        self.is_quick_play_realms: bool = settings.is_quick_play_realms
        self.maximum_heap_size: int = settings.maximum_heap_size
        self.initial_heap_size: int = settings.initial_heap_size
        self.auth_player_name: str = settings.auth_player_name
        self.auth_uuid: str = settings.auth_uuid
        self.auth_access_token: str = settings.auth_access_token
        self.user_type: str = settings.user_type
        self.quick_play_path: pathlib.Path = settings.quick_play_path if settings.quick_play_path is not None \
            else settings.working_path / "quickPlay" / "log.json"
        self.quick_play_singleplayer: str = settings.quick_play_singleplayer
        self.quick_play_multiplayer: str = settings.quick_play_multiplayer
        self.quick_play_realms: str = settings.quick_play_realms

        self.version_metadata: dict = {}
        self.final_argument: str = ""

    def generate_launch_argument(self) -> int:
        start_time: float = time.time()

        with open(self.working_path / "versions" / self.version / f"{self.version}.json") as file:
            self.version_metadata = json.load(file)

        self._launch_tasks_init()
        self.task_queue.run()
        self.task_queue.shutdown()

        replacements: dict = {
            # JVM 参数
            "natives_directory": f"\"{self.natives_directory}\"",
            "launcher_name": f"\"{self.launcher_name}\"",
            "launcher_version": self.launcher_version,
            "classpath": self.task_queue.results["1"],
            "xmn": self.maximum_heap_size,
            "xmx": self.initial_heap_size,

            # 游戏参数
            "auth_player_name": self.auth_player_name,
            "version_name": f"\"{self.version}\"",
            "game_directory": f"\"{self.working_path}\"",
            "assets_root": f"\"{self.working_path / 'assets'}\"",
            "assets_index_name": self.version_metadata["assetIndex"]["id"],
            "auth_uuid": self.auth_uuid,
            "auth_access_token": self.auth_access_token,
            "user_type":self.user_type,
            "version_type": self.version_metadata["type"],
            "clientid": "0",  # noqa
            "auth_xuid": "0",  # noqa
            "quickPlayPath": f"\"{self.quick_play_path}\"",
            "quickPlaySingleplayer": self.quick_play_singleplayer,
            "quickPlayMultiplayer": self.quick_play_multiplayer,
            "quickPlayRealms": self.quick_play_realms,
        }

        final_argument: str = \
            f"{self.task_queue.results["0"]} {self.task_queue.results["2"]}".replace("${", "{")
        final_argument = final_argument.format(**replacements)
        self.logger.info(f"启动参数解析耗时 {time.time() - start_time:.3f}s")
        self.logger.info(final_argument)
        self.final_argument = final_argument

        return 0

    def analyze_jvm_argument(self) -> str:
        jvm_argument: str = self.jvm_argument_head

        if "arguments" not in self.version_metadata:
            jvm: list = [
                {
                    "rules": [
                        {
                            "action": "allow",
                            "os": {
                                "name": "osx"
                            }
                        }
                    ],
                    "value": [
                        "-XstartOnFirstThread"
                    ]
                },
                {
                    "rules": [
                        {
                            "action": "allow",
                            "os": {
                                "name": "windows"
                            }
                        }
                    ],
                    "value": "-XX:HeapDumpPath=MojangTricksIntelDriversForPerformance_javaw.exe_minecraft.exe.heapdump"
                },
                {
                    "rules": [
                        {
                            "action": "allow",
                            "os": {
                                "arch": "x86"
                            }
                        }
                    ],
                    "value": "-Xss1M"
                },
                "-Djava.library.path=${natives_directory}",
                "-Djna.tmpdir=${natives_directory}",
                "-Dorg.lwjgl.system.SharedLibraryExtractPath=${natives_directory}",
                "-Dio.netty.native.workdir=${natives_directory}",
                "-Dminecraft.launcher.brand=${launcher_name}",
                "-Dminecraft.launcher.version=${launcher_version}",
                "-cp",
                "${classpath}"
            ]
        else:
            jvm: list = self.version_metadata["arguments"]["jvm"]

        argument_list: list[str] = []
        for argument_information in jvm:
            if type(argument_information) is dict:
                is_eligible: bool = True
                for rule in argument_information["rules"]:
                    if not self._analysis_rules(rule):
                        is_eligible = False
                        break
                if not is_eligible:
                    continue

                if type(argument_information["value"]) is list:
                    for argument in argument_information["value"]:
                        argument_list.append(f"\"{argument}\"" if " " in argument else argument)
                else:
                    argument_list.append(
                        f"\"{argument_information["value"]}\""
                        if " " in argument_information["value"]
                        else argument_information["value"]
                    )
            else:
                argument_list.append(
                    f"\"{argument_information}\"" if " " in argument_information else argument_information
                )

        jvm_argument = (f"{jvm_argument} {' '.join(argument_list)} "
                        f"{' '.join([f'-Xmx{str(self.maximum_heap_size)}M', f'-Xms{str(self.initial_heap_size)}M'])} "
                        f"{self.version_metadata['mainClass']}")

        return jvm_argument

    def analyze_libraries(self) -> str:
        self.natives_directory.mkdir(parents=True, exist_ok=True)
        library_path: pathlib.Path = self.working_path / "libraries"
        native_libraries: list = []
        libraries: list = []
        # 1.19-pre1 的更改太大了，基本没法合并成一个逻辑
        if (datetime.datetime.fromisoformat(self.version_metadata["releaseTime"])
                >= datetime.datetime.fromisoformat("2022-05-18T13:51:54+00:00")):
            for library in self.version_metadata["libraries"]:
                current_library_maven: list[str] = library["name"].split(":")
                current_library_path: pathlib.Path = \
                    pathlib.Path() / current_library_maven[0].replace(".", "/") / current_library_maven[1] / \
                    current_library_maven[2] / f"{current_library_maven[1]}-{current_library_maven[2]}.jar"

                if "rules" in library.keys():
                    is_eligible: bool = True
                    for rule in library["rules"]:
                        if not self._analysis_rules(rule):
                            is_eligible = False
                            break
                    if not is_eligible:
                        continue
                    native_libraries.append(library_path / current_library_path)

                libraries.append(library_path / current_library_path)
        else:
            for library in self.version_metadata["libraries"]:
                current_library_maven: list[str] = library["name"].split(":")
                current_library_path: pathlib.Path = \
                    pathlib.Path() / current_library_maven[0].replace(".", "/") / current_library_maven[1] / \
                    current_library_maven[2] / f"{current_library_maven[1]}-{current_library_maven[2]}.jar"

                if "rules" in library.keys():
                    is_eligible: bool = True
                    for rule in library["rules"]:
                        if not self._analysis_rules(rule):
                            is_eligible = False
                            break
                    if not is_eligible:
                        continue
                if "natives" in library.keys():
                    libraries.append(str(
                        library_path /
                        library["downloads"]["classifiers"][library["natives"][self.system_name]]["path"]
                    ))
                    native_libraries.append(str(
                        library_path /
                        library["downloads"]["classifiers"][library["natives"][self.system_name]]["path"]
                    ))
                if "downloads" in library:
                    if "artifact" in library["downloads"].keys():
                        libraries.append(str(library_path / current_library_path))
                else:
                    libraries.append(str(library_path / current_library_path))
            self._unzip_native_libraries(native_libraries)

        libraries.append(str(self.working_path / "versions" / self.version / f"{self.version}.jar"))
        classpath: str = os.pathsep.join(libraries)
        classpath = f"\"{classpath}\""

        return classpath

    def analyze_game_argument(self) -> str:
        if "arguments" not in self.version_metadata:
            game_argument = self.version_metadata["minecraftArguments"]
        else:
            argument_list: list[str] = []
            for argument_information in self.version_metadata["arguments"]["game"]:
                if "rules" in argument_information:
                    is_eligible: bool = True
                    for rule in argument_information["rules"]:
                        if not self._analysis_rules(rule):
                            is_eligible: bool = False
                            break
                    if not is_eligible:
                        continue
                if type(argument_information) is dict:
                    if type(argument_information["value"]) is list:
                        for argument in argument_information["value"]:
                            argument_list.append(argument)
                    else:
                        argument_list.append(argument_information["value"])
                else:
                    argument_list.append(argument_information)

            game_argument: str = " ".join(argument_list)

        return game_argument

    def _launch_tasks_init(self) -> None:
        self.task_queue.submit({
            "id": "0",
            "description": "解析 JVM 参数",
            "function": self.analyze_jvm_argument,
            "args": (),
            "priority": 10
        })
        self.task_queue.submit({
            "id": "1",
            "description": "解析支持库",
            "function": self.analyze_libraries,
            "args": (),
            "priority": 10
        })
        self.task_queue.submit({
            "id": "2",
            "description": "解析游戏参数",
            "function": self.analyze_game_argument,
            "args": (),
            "priority": 10
        })

    def _unzip_native_libraries(self, native_libraries: list[pathlib.Path]) -> None:
        # shutil.rmtree(self.natives_directory)
        self.natives_directory.mkdir(parents=True, exist_ok=True)
        (self.temp_path / "launches" / "native_libraries" / self.version).mkdir(parents=True, exist_ok=True)

        for native_library in native_libraries:
            with zipfile.ZipFile(native_library, "r") as zip_ref:
                zip_ref.extractall(self.temp_path / "launches" / "native_libraries" / self.version)

        files: list[pathlib.Path] = []
        extensions: list[str] = [
            ".dll",
            ".so",
            ".jnilib",
            ".dylib",
        ]
        for path in (self.temp_path / "launches" / "native_libraries" / self.version).rglob("*"):
            if path.is_file():
                if path.suffix in extensions:
                    files.append(path)
        for file in files:
            shutil.copy2(file, self.natives_directory)
        shutil.rmtree(self.temp_path / "launches" / "native_libraries" / self.version)

    def _analysis_rules(self, rules: dict) -> bool:
        if not rules:
            return True
        is_eligible: bool = True

        if "os" in rules.keys():
            if "name" in rules["os"].keys():
                if self.system_name != rules["os"]["name"]:
                    is_eligible = False
            elif "version" in rules["os"].keys():
                if not re.match(rules["os"]["version"], self.system_version):
                    is_eligible = False
            elif "arch" in rules["os"].keys():
                if not re.match(rules["os"]["arch"], self.system_architecture):
                    is_eligible = False
        elif "features" in rules.keys():
            for i in range(len(rules["features"])):
                if not getattr(self, tuple(rules["features"].keys())[i], False) == tuple(rules["features"].values())[i]:
                    is_eligible = False

        if is_eligible:
            if rules["action"] == "allow":
                is_enabled = True
            else:
                is_enabled = False
        else:
            if rules["action"] == "allow":
                is_enabled = False
            else:
                is_enabled = True

        return is_enabled

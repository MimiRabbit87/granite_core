from __future__ import annotations
import zipfile
import json
import pathlib
import re
import logging
import shutil
import datetime


class MinecraftLauncher:
    def __init__(
            self,
            temp_path: pathlib.Path,
            system_name: str,
            system_version: str,
            system_architecture: str,
            working_path: pathlib.Path,
            version: str,
            jvm_argument_head: str,
            is_demo_user: bool,
            has_custom_resolution: bool,
            has_quick_plays_support: bool,
            is_quick_play_singleplayer: bool,
            is_quick_play_multiplayer: bool,
            is_quick_play_realms: bool,
            maximum_heap_size: int,  # 单位：MB
            initial_heap_size: int,  # 单位：MB
            auth_player_name: str,
            auth_uuid: str,
            auth_access_token: str,
            user_type: str,
            quick_play_path: pathlib.Path | None = None,
            quick_play_singleplayer: str = "",
            quick_play_multiplayer: str = "",
            quick_play_realms: str = "",
    ) -> None:
        self.natives_directory: pathlib.Path = working_path / "versions" / version / f"{version}-natives"
        self.launcher_name: str = "Granite"
        self.launcher_version: str = "114514"
        self.classpath: str = ""

        self.temp_path: pathlib.Path = temp_path
        self.system_name: str = system_name
        self.system_version: str = system_version
        self.system_architecture: str = system_architecture
        self.working_path: pathlib.Path = working_path
        self.version: str = version
        self.jvm_argument_head: str = jvm_argument_head
        self.is_demo_user: bool = is_demo_user
        self.has_custom_resolution: bool = has_custom_resolution
        self.has_quick_plays_support: bool = has_quick_plays_support
        self.is_quick_play_singleplayer: bool = is_quick_play_singleplayer
        self.is_quick_play_multiplayer: bool = is_quick_play_multiplayer
        self.is_quick_play_realms: bool = is_quick_play_realms
        self.maximum_heap_size: int = maximum_heap_size
        self.initial_heap_size: int = initial_heap_size
        self.auth_player_name: str = auth_player_name
        self.auth_uuid: str = auth_uuid
        self.auth_access_token: str = auth_access_token
        self.user_type: str = user_type
        self.quick_play_path: pathlib.Path = quick_play_path if quick_play_path is not None \
            else working_path / "quickPlay" / "log.json"
        self.quick_play_singleplayer: str = quick_play_singleplayer
        self.quick_play_multiplayer: str = quick_play_multiplayer
        self.quick_play_realms: str = quick_play_realms

    def launch(self) -> int:
        jvm_argument: str = self.jvm_argument_head
        game_argument: str = ""

        with open(self.working_path / "versions" / self.version / f"{self.version}.json") as file:
            version_metadata: dict = json.load(file)

        if "arguments" not in version_metadata:
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
            jvm: list = version_metadata["arguments"]["jvm"]
        for argument_information in jvm:
            current_argument = ""
            if type(argument_information) is dict:
                is_eligible: bool = True
                for rule in argument_information["rules"]:
                    if not self._analysis_rules(rule):
                        is_eligible = False
                        break
                if not is_eligible:
                    continue
            if type(argument_information) is dict:
                if type(argument_information["value"]) is list:
                    for argument in argument_information["value"]:
                        current_argument += f" {argument}"
                else:
                    current_argument = argument_information["value"]
            else:
                current_argument = argument_information
            jvm_argument += f" {current_argument}"

        self.natives_directory.mkdir(parents=True, exist_ok=True)
        library_path: pathlib.Path = self.working_path / "libraries"
        native_libraries: list = []
        libraries: list = []
        if (datetime.datetime.fromisoformat(version_metadata["releaseTime"])
            >= datetime.datetime.fromisoformat("2022-05-18T13:51:54+00:00")):
            for library in version_metadata["libraries"]:
                if "rules" in library.keys():
                    is_eligible: bool = True
                    for rule in library["rules"]:
                        if not self._analysis_rules(rule):
                            is_eligible = False
                            break
                    if not is_eligible:
                        continue
                    native_libraries.append(library_path / library["downloads"]["artifact"]["path"])

                libraries.append(library_path / library["downloads"]["artifact"]["path"])
        else:
            for library in version_metadata["libraries"]:
                if "rules" in library.keys():
                    is_eligible: bool = True
                    for rule in library["rules"]:
                        if not self._analysis_rules(rule):
                            is_eligible = False
                            break
                    if not is_eligible:
                        continue
                if "natives" in library.keys():
                    libraries.append(
                        library_path /
                        library["downloads"]["classifiers"][library["natives"][self.system_name]]["path"]
                    )
                    native_libraries.append(
                        library_path /
                        library["downloads"]["classifiers"][library["natives"][self.system_name]]["path"]
                    )
                if "artifact" in library["downloads"].keys():
                    libraries.append(library_path / library["downloads"]["artifact"]["path"])
            self._unzip_native_libraries(native_libraries)

        libraries.append(self.working_path / "versions" / self.version / f"{self.version}.jar")
        classpath: str = str(libraries[0])
        for library in libraries[1:]:
            classpath += f";{str(library)}" if self.system_name == "windows" else f":{str(library)}"
        classpath = f'"{classpath}"'

        jvm_argument += (f" -Xmx{str(self.maximum_heap_size)}M"
                         f" -Xms{str(self.initial_heap_size)}M"
                         f' {version_metadata["mainClass"]}')

        if "arguments" not in version_metadata:
            game_argument = version_metadata["minecraftArguments"]
        else:
            for argument_information in version_metadata["arguments"]["game"]:
                current_argument: str = ""
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
                            current_argument += f" {argument}"
                    else:
                        current_argument = argument_information["value"]
                else:
                    current_argument = argument_information
                game_argument += f" {current_argument}"
            game_argument = game_argument.strip()

        replacements: dict = {
            # JVM 参数
            "natives_directory": f'"{self.natives_directory}"',
            "launcher_name": f'"{self.launcher_name}"',
            "launcher_version": self.launcher_version,
            "classpath": classpath,
            "xmn": self.maximum_heap_size,
            "xmx": self.initial_heap_size,

            # 游戏参数
            "auth_player_name": self.auth_player_name,
            "version_name": f'"{self.version}"',
            "game_directory": f'"{self.working_path}"',
            "assets_root": f'"{self.working_path / "assets"}"',
            "assets_index_name": version_metadata["assetIndex"]["id"],
            "auth_uuid": self.auth_uuid,
            "auth_access_token": self.auth_access_token,
            "user_type":self.user_type,
            "version_type": version_metadata["type"],
            "clientid": "0",
            "auth_xuid": "0",
            "quickPlayPath": f'"{self.quick_play_path}"',
            "quickPlaySingleplayer": self.quick_play_singleplayer,
            "quickPlayMultiplayer": self.quick_play_multiplayer,
            "quickPlayRealms": self.quick_play_realms,
        }
        final_argument: str = f"{jvm_argument} {game_argument}".replace("${", "{")
        final_argument = final_argument.format(**replacements)
        logging.info(final_argument)

        return 0

    def _unzip_native_libraries(self, native_libraries: list[pathlib.Path]) -> None:
        # shutil.rmtree(self.natives_directory)
        self.natives_directory.mkdir(parents=True, exist_ok=True)
        (self.temp_path / "launches" / "native_libraries" / self.version).mkdir(parents=True, exist_ok=True)

        for native_library in native_libraries:
            with zipfile.ZipFile(native_library, 'r') as zip_ref:
                zip_ref.extractall(self.temp_path / "launches" / "native_libraries" / self.version)

        files: list[pathlib.Path] = []
        extensions: list[str] = [
            ".dll",
            ".so",
            ".jnilib",
            ".dylib",
        ]
        for path in (self.temp_path / "launches" / "native_libraries" / self.version).rglob('*'):
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

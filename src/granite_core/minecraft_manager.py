import json
import pathlib


class MinecraftManager:
    """
    管理 Minecraft 用的
    """
    def __init__(self, current_version: str) -> None:
        self.current_version: str = current_version
        self.current_game_directory: pathlib.Path = pathlib.Path()
        self.game_metadata: dict = {}

    def analyze_game_metadata(self, data_file_path: pathlib.Path) -> None:  # 诶呀这元数据可甚是美味啊
        with open(str(data_file_path), "r") as file:
            self.game_metadata = json.load(file)

    def get_game_version(self): ...

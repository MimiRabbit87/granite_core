import json
import unittest

import granite_core  # 当当前工作目录为项目根目录时，运行 pip install -e .


class Test(unittest.TestCase):
    @unittest.skip
    def test1(self) -> None:
        setting: granite_core.granite_settings.GraniteSettings = granite_core.granite_settings.GraniteSettings()
        installer: granite_core.minecraft_installer.MinecraftInstaller = granite_core.minecraft_installer.MinecraftInstaller(
            setting.working_path,
            "1.12.2",
            "Mojang",
            setting.max_workers,
            setting.temp_path
        )
        installer.install()
        tasks = []
        for i in range(len(original_tasks := installer.install_queue.get_original_tasks())):
            tasks.append({
                "id": original_tasks[i][2]["id"],
                "description": original_tasks[i][2]["description"]
            })
        with open("test_results.json", "w") as file:
            json.dump(
                {
                    "tasks": tasks,
                    "results": installer.install_queue.get_results()
                },
                file,
                indent=2
            )

    # @unittest.skip
    def test2(self) -> None:
        setting: granite_core.granite_settings.GraniteSettings = granite_core.granite_settings.GraniteSettings()
        launcher: granite_core.minecraft_launcher.MinecraftLauncher = granite_core.minecraft_launcher.MinecraftLauncher(
            setting.temp_path,
            setting.system_name,
            setting.system_version,
            setting.system_architecture,
            setting.working_path,
            "1.12.2",
            setting.jvm_argument_head,
            False,
            False,
            False,
            False,
            False,
            False,
            8192,
            4096,
            "MimiRabbit87",
            "adf65cb8e281447397e7a55a62c934d7",
            "eyJra"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            "XXXXXXX",
            "msa",
        )

        launcher.launch()


if __name__ == "__main__":
    unittest.main()

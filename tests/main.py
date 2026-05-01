import json
import logging

import unittest

import granite_core  # 当当前工作目录为项目根目录时，运行 pip install -e .

logging.basicConfig(level=logging.INFO, format='[%(asctime)s][%(levelname)s][%(name)s]: %(message)s', encoding="utf-8")


class Test(unittest.TestCase):
    @unittest.skip
    def test_install(self) -> None:
        setting: granite_core.granite_settings.GraniteSettings = granite_core.granite_settings.GraniteSettings()
        installer: granite_core.minecraft_install.MinecraftInstall = (
            granite_core.minecraft_install.MinecraftInstall(
            setting.working_path,
            "1.12.2",
            "Mojang",
            setting.max_workers,
            setting.temp_path
        ))
        installer.install()
        tasks = []
        for i in range(len(original_tasks := installer.install_queue.original_tasks)):
            tasks.append({
                "id": original_tasks[i][2]["id"],
                "description": original_tasks[i][2]["description"]
            })
        with open("test_results.json", "w") as file:
            json.dump(
                {
                    "tasks": tasks,
                    "results": installer.install_queue.results
                },
                file,
                indent=2
            )

    @unittest.skip
    def test_launch(self) -> None:
        setting: granite_core.granite_settings.GraniteSettings = granite_core.granite_settings.GraniteSettings()
        setting.current_version = "1.12.2"
        launcher: granite_core.minecraft_launch.MinecraftLaunch = granite_core.minecraft_launch.MinecraftLaunch(
            setting
        )

        launcher.launch()

    # @unittest.skip
    def test_login(self) -> None:
        setting: granite_core.granite_settings.GraniteSettings = granite_core.granite_settings.GraniteSettings()
        login: granite_core.account_login.AccountLogin = granite_core.account_login.AccountLogin(setting)
        login.login()


if __name__ == "__main__":
    unittest.main()

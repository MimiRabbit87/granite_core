import json
import logging

import unittest

import granite_core  # 当当前工作目录为项目根目录时，运行 pip install -e .

logging.basicConfig(level=logging.INFO, format='[%(asctime)s][%(levelname)s][%(name)s]: %(message)s', encoding="utf-8")


class Test(unittest.TestCase):
    def setUp(self) -> None:
        self.logger: logging.Logger = logging.getLogger("Test")
        self.thread_pool: granite_core.thread_pool.ThreadPool = granite_core.thread_pool.ThreadPool(max_workers=16)

    @unittest.skip
    def test_install(self) -> None:
        setting: granite_core.granite_settings.GraniteSettings = granite_core.granite_settings.GraniteSettings()
        installer: granite_core.minecraft_install.MinecraftInstall = (
                granite_core.minecraft_install.MinecraftInstall(
                setting,
                "1.12.2",
                16,
                self.thread_pool
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

    # @unittest.skip
    def test_launch(self) -> None:
        setting: granite_core.granite_settings.GraniteSettings = granite_core.granite_settings.GraniteSettings()
        setting.current_version = "1.16.5-Fabric 0.19.2"
        setting.user_type = "msa"
        setting.auth_player_name = "MimiRabbit87"
        setting.auth_uuid = "f008073df78f464ea3a986f0d88d1f28"
        # login: granite_core.account_login.AccountLogin = \
        #     granite_core.account_login.AccountLogin(setting, self.thread_pool)
        # login.login()
        # setting.auth_access_token = login.task_queue.results['4']['Token']
        launcher: granite_core.minecraft_launch.MinecraftLaunch = granite_core.minecraft_launch.MinecraftLaunch(
            setting,
            self.thread_pool
        )

        launcher.launch()
        self.thread_pool.shutdown()

    @unittest.skip
    def test_login(self) -> None:
        setting: granite_core.granite_settings.GraniteSettings = granite_core.granite_settings.GraniteSettings()
        login: granite_core.account_login.AccountLogin = \
            granite_core.account_login.AccountLogin(setting, self.thread_pool)
        if login.login():
            self.logger.info(f"登录成功，访问令牌：{login.task_queue.results['4']['Token']}")
        else:
            self.logger.info("登录失败")

        tasks = []
        for i in range(len(original_tasks := login.task_queue.original_tasks)):
            tasks.append({
                "id": original_tasks[i][2]["id"],
                "description": original_tasks[i][2]["description"]
            })
        with open("test_results.json", "w") as file:
            json.dump(
                {
                    "tasks": tasks,
                    "results": login.task_queue.results
                },
                file,
                indent=2
            )

        self.thread_pool.shutdown()


if __name__ == "__main__":
    unittest.main()

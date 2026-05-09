"""
    Main: the main file of unittest.
    Copyright (C) 2026 MimiRabbit

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import subprocess

import unittest

import granite_core  # 当当前工作目录为项目根目录时，运行 pip install -e .

logging.basicConfig(level=logging.INFO, format='[%(asctime)s][%(levelname)s][%(name)s]: %(message)s', encoding="utf-8")


class Test(unittest.TestCase):
    def setUp(self) -> None:
        self.logger: logging.Logger = logging.getLogger("Test")
        self.thread_pool: concurrent.futures.ThreadPoolExecutor = concurrent.futures.ThreadPoolExecutor(max_workers=16)

    @unittest.skip
    def test_install(self) -> None:
        settings: granite_core.granite.granite_settings.GraniteSettings = \
            granite_core.granite.granite_settings.GraniteSettings()
        installer: granite_core.minecraft.minecraft_installation.MinecraftInstallation = (
                granite_core.minecraft.minecraft_installation.MinecraftInstallation(
                settings,
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

        self.thread_pool.shutdown()

    @unittest.skip
    def test_launch(self) -> None:
        settings: granite_core.granite.granite_settings.GraniteSettings = \
            granite_core.granite.granite_settings.GraniteSettings()
        settings.current_version = "1.16.5-Fabric 0.19.2"
        settings.user_type = "msa"
        settings.auth_player_name = "MimiRabbit87"
        settings.auth_uuid = "f008073df78f464ea3a986f0d88d1f28"
        # login: granite_core.account_login.AccountLogin = \
        #     granite_core.account_login.AccountLogin(settings, self.thread_pool)
        # login.login()
        # settings.auth_access_token = login.task_queue.results["4"]["access_token"]
        launcher: granite_core.minecraft.minecraft_launch.MinecraftLaunch = \
            granite_core.minecraft.minecraft_launch.MinecraftLaunch(
                settings,
                self.thread_pool
            )

        launcher.generate_launch_argument()
        self.thread_pool.shutdown()

    @unittest.skip
    def test_login(self) -> None:
        settings: granite_core.granite.granite_settings.GraniteSettings = \
            granite_core.granite.granite_settings.GraniteSettings()
        login: granite_core.account.account_login.AccountLogin = \
            granite_core.account.account_login.AccountLogin(settings, self.thread_pool)
        if login.login():
            self.logger.info(f"登录成功，访问令牌：{login.task_queue.results['4']['access_token'][:4]}……")
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

    @unittest.skip
    def test_search_for_game_instance(self) -> None:
        manager: granite_core.minecraft.minecraft_instance_management.MinecraftInstanceManagement = \
            granite_core.minecraft.minecraft_instance_management.MinecraftInstanceManagement()
        manager.search_for_game_instances()
        self.logger.info(manager.external_instances_list)

        self.thread_pool.shutdown()

    @unittest.skip
    def test_search_for_java(self) -> None:
        settings: granite_core.granite.granite_settings.GraniteSettings = \
            granite_core.granite.granite_settings.GraniteSettings()
        manager: granite_core.java.java_management.JavaManagement = \
            granite_core.java.java_management.JavaManagement(settings, self.thread_pool)

        manager.search_for_java()

        self.thread_pool.shutdown()

    # @unittest.skip
    def test_complete_launch_process(self) -> None:
        try:
            settings: granite_core.granite.granite_settings.GraniteSettings = \
                granite_core.granite.granite_settings.GraniteSettings()

            settings.current_version = "1.21.11"
            settings.user_type = "msa"
            settings.auth_player_name = "MimiRabbit87"
            settings.auth_uuid = "f008073df78f464ea3a986f0d88d1f28"

            java_manager: granite_core.java.java_management.JavaManagement = \
                granite_core.java.java_management.JavaManagement(settings, self.thread_pool)
            minecraft_instance_manager: \
                granite_core.minecraft.minecraft_instance_management.MinecraftInstanceManagement = \
                granite_core.minecraft.minecraft_instance_management.MinecraftInstanceManagement()

            login: granite_core.account.account_login.AccountLogin = \
                granite_core.account.account_login.AccountLogin(settings, self.thread_pool)
            if login.login():
                self.logger.info(f"登录成功，访问令牌：{login.task_queue.results['4']['access_token'][:5]}……")
            else:
                self.logger.info("登录失败")
                self.thread_pool.shutdown()
                return

            settings.auth_access_token = login.task_queue.results["4"]["access_token"]

            launcher: granite_core.minecraft.minecraft_launch.MinecraftLaunch = \
                granite_core.minecraft.minecraft_launch.MinecraftLaunch(
                    settings,
                    self.thread_pool
                )
            launcher.generate_launch_argument()

            java_manager.search_for_java()
            minecraft_instance: subprocess.Popen = minecraft_instance_manager.launch_game(
                list(java_manager.java_list.keys())[0],
                launcher.final_argument
            )
            self.thread_pool.submit(minecraft_instance_manager._read_stdout, minecraft_instance)
            minecraft_instance.wait()

            minecraft_instance.stdout.close()
        except Exception:  # noqa
            self.logger.exception("在单元测试中发生了未预料的异常：")
        self.thread_pool.shutdown()


if __name__ == "__main__":
    unittest.main()

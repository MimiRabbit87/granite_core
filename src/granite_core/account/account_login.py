"""
    Account Login: the implement of logic of account login.
    Copyright (C) 2026 MimiRabbit

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from __future__ import annotations

import concurrent.futures
import logging
import time
import webbrowser

import pyperclip
import requests

from granite_core.concurrency import task_queue
from granite_core.granite import granite_settings


class AccountLogin:
    def __init__(
            self,
            settings: granite_settings.GraniteSettings,
            thread_pool_: concurrent.futures.ThreadPoolExecutor
    ) -> None:
        self.logger: logging.Logger = logging.getLogger("Login")
        self.running_flag: bool = True
        self.settings: granite_settings.GraniteSettings = settings
        self.task_queue: task_queue.TaskQueue = task_queue.TaskQueue(4, thread_pool_)

    def login(self) -> bool:
        self._login_tasks_init()
        self.task_queue.run()
        if self.running_flag:
            self.task_queue.shutdown()
            return True
        else:
            return False

    def msa_get_device_code(self) -> dict[str, str]:
        self.logger.info("使用设备代码流进行微软账户登录")
        self.logger.info("微软账户登录流程一：获取设备代码对")
        headers: dict[str, str] = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data: dict[str, str] = {
            "client_id": self.settings.azure_client_id,
            "scope": "XboxLive.signin offline_access"
        }

        response: requests.Response = requests.post(
            "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode", headers=headers, data=data
        )

        if response.status_code == 200:
            self.logger.info(f"设备代码对获取完成：{response.json()['user_code']}")
            pyperclip.copy(response.json()["user_code"])
            self.logger.info(f"已尝试将设备代码对复制至剪贴板")
            webbrowser.open(response.json()["verification_uri"])
            self.logger.info(f"已尝试使用浏览器打开 {response.json()['verification_uri']}")
            return response.json()
        else:
            self.logger.error(f"在获取设备代码对时发生错误：错误的响应状态码：{response.status_code}")
            # 登录失败
            self.running_flag = False
            self.task_queue.shutdown()
            raise

    def msa_get_user_authorization_status(self) -> dict[str, str]:
        self.logger.info("微软账户登录流程二：轮询用户授权状态")
        device_info: dict[str, str | int] = self.task_queue.results["0"]
        device_code: str = device_info["device_code"]
        interval: float = float(device_info["interval"])
        expires_in: float = float(device_info["expires_in"])
        start_time: float = time.time()
        self.logger.info(f"每次轮询间隔 {interval}s，有效期为 {expires_in}s")

        while time.time() - start_time < expires_in:
            result: dict = self._msa_authorization_polling(device_code)

            if "access_token" in result:
                self.logger.info("用户授权成功")
                return result

            error: str = result.get("error")
            if error == "authorization_pending":
                wait: float = float(result.get("interval", interval))
                time.sleep(wait)
            elif error == "slow_down":
                interval += 1
                self.logger.debug(f"收到 slow_down 信号，新间隔 {interval}s")
                time.sleep(interval)
            else:
                self.logger.error(f"轮询请求中包含意外的错误码：{result}")
                self.running_flag = False
                raise

        self.logger.error(f"在轮询用户授权状态时发生错误：授权超时：用户授权应在 {expires_in}s 内完成")
        raise TimeoutError("授权超时")

    def _msa_authorization_polling(self, device_code: str) -> dict:
        if not self.running_flag:
            return {}

        headers: dict[str, str] = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data: dict[str, str] = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": self.settings.azure_client_id,
            "device_code": device_code
        }

        response = requests.post(
            "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
            headers=headers, data=data
        )

        return response.json()

    def msa_xbox_live_authorize(self) -> dict:
        if not self.running_flag:
            return {}

        self.logger.info("微软账户登录流程三：Xbox Live 身份验证")
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        payload: dict[str, str] = {
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",  # noqa
                "RpsTicket": f"d={self.task_queue.results['1']['access_token']}"
            },
            "RelyingParty": "http://auth.xboxlive.com",  # noqa
            "TokenType": "JWT"
        }

        response = requests.post(
            "https://user.auth.xboxlive.com/user/authenticate",
            headers=headers, json=payload
        )

        return response.json()

    def msa_xsts_authorize(self) -> dict:  # noqa
        if not self.running_flag:
            return {}

        self.logger.info("微软账户登录流程四：XSTS 身份验证")  # noqa
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        payload: dict[str, str] = {
            "Properties": {
                "SandboxId": "RETAIL",
                "UserTokens": [
                    self.task_queue.results["2"]["Token"]
                ]
            },
            "RelyingParty": "rp://api.minecraftservices.com/",  # noqa
            "TokenType": "JWT"
        }

        response = requests.post(
            "https://xsts.auth.xboxlive.com/xsts/authorize",
            headers=headers, json=payload
        )

        return response.json()

    def msa_get_game_access_token(self) -> dict:
        if not self.running_flag:
            return {}

        self.logger.info("微软账户登录流程五：获取 Minecraft 访问令牌")
        body: dict[str, str] = {
            "identityToken": f"XBL3.0 x={self.task_queue.results['2']['DisplayClaims']['xui'][0]['uhs']};"
                             f"{self.task_queue.results['3']['Token']}"
        }

        response = requests.post(
            "https://api.minecraftservices.com/authentication/login_with_xbox",
            json=body
        )

        return response.json()

    def _login_tasks_init(self) -> None:
        self.task_queue.submit({
            "id": "0",
            "description": "获取代码对",
            "function": self.msa_get_device_code,
            "args": (),
            "priority": 10
        })
        self.task_queue.submit({
            "id": "1",
            "description": "获取用户授权状态",
            "function": self.msa_get_user_authorization_status,
            "args": (),
            "pre_tasks": ["0"],
            "priority": 10
        })
        self.task_queue.submit({
            "id": "2",
            "description": "Xbox Live 身份验证",
            "function": self.msa_xbox_live_authorize,
            "args": (),
            "pre_tasks": ["1"],
            "priority": 10
        })
        self.task_queue.submit({
            "id": "3",
            "description": "XSTS 身份验证",  # noqa
            "function": self.msa_xsts_authorize,
            "args": (),
            "pre_tasks": ["2"],
            "priority": 10
        })
        self.task_queue.submit({
            "id": "4",
            "description": "获取 Minecraft 访问令牌",
            "function": self.msa_get_game_access_token,
            "args": (),
            "pre_tasks": ["3"],
            "priority": 10
        })

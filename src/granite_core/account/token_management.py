"""
    Token Management: manages tokens.
    Copyright (C) 2026 MimiRabbit

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from __future__ import annotations

import logging
import time

import keyring
import keyring.errors


class TokenManagement:
    SERVICE_NAME: str = "Granite Core"

    logger: logging.Logger

    def __init__(self) -> None:
        self.logger = logging.getLogger("TokenManagement")

    def save_token(self, player_uuid: str, token: str, usage: str, time_limit_seconds: int=-1) -> None:
        keyring.set_password(self.SERVICE_NAME, f"{usage}@{player_uuid}", token)
        if time_limit_seconds == -1:
            keyring.set_password(self.SERVICE_NAME, f"{usage}@{player_uuid}_time_limit", "inf")
            self.logger.info(f"已保存玩家 UUID {player_uuid} 用途为 {usage} 的令牌，永不过期")
        else:
            keyring.set_password(
                self.SERVICE_NAME,
                f"{usage}@{player_uuid}_time_limit",
                str(time_limit_seconds + time.time())
            )
            self.logger.info(f"已保存玩家 UUID {player_uuid} 用途为 {usage} 的令牌，时效 {time_limit_seconds}s")

    def load_token(self, player_uuid: str, usage: str) -> str | None:
        token: str | None = keyring.get_password(self.SERVICE_NAME, f"{usage}@{player_uuid}")

        if token is None:
            self.logger.warning(f"玩家 UUID {player_uuid} 用途为 {usage} 的令牌为空")
            return None

        expires_at: str | None = keyring.get_password(self.SERVICE_NAME, f"{usage}@{player_uuid}_time_limit")

        if expires_at is None:
            self.logger.warning(f"玩家 UUID {player_uuid} 用途为 {usage} 的令牌无效")
            return None

        expires_at: float = float(expires_at)

        if time.time() <= expires_at:
            self.logger.info(f"已获取玩家 UUID {player_uuid} 用途为 {usage} 的令牌")
            return token
        else:
            self.logger.info(f"玩家 UUID {player_uuid} 用途为 {usage} 的令牌已过期")
            return None

    def delete_token(self, player_uuid: str, usage: str) -> bool:
        try:
            keyring.delete_password(self.SERVICE_NAME, f"{usage}@{player_uuid}")
            self.logger.info(f"已删除玩家 UUID {player_uuid} 用途为 {usage} 的令牌")
        except keyring.errors.PasswordDeleteError:
            self.logger.warning(
                f"在尝试删除玩家 UUID {player_uuid} 用途为 {usage} 的令牌时抛出异常：键名为 {usage}@{player_uuid} 的令牌不存在"
            )
            return False

        try:
            keyring.delete_password(self.SERVICE_NAME, f"{usage}@{player_uuid}_time_limit")
        except keyring.errors.PasswordDeleteError:
            pass

        return True

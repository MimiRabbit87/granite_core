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

import keyring
import keyring.errors


class TokenManagement:
    SERVICE_NAME: str = "Granite Core"

    def __init__(self) -> None:
        self.logger = logging.getLogger("TokenManagement")

    def save_token(self, player_uuid: str, token: str, usage: str) -> None:
        keyring.set_password(self.SERVICE_NAME, f"{usage}@{player_uuid}", token)
        self.logger.info(f"已保存玩家 UUID {player_uuid} 用途为 {usage} 的令牌")

    def load_token(self, player_uuid: str, usage: str) -> str | None:
        token: str | None = keyring.get_password(self.SERVICE_NAME, f"{usage}@{player_uuid}")
        self.logger.info(f"已获取玩家 UUID {player_uuid} 用途为 {usage} 的令牌")
        if token is None:
            self.logger.warning(f"玩家 UUID {player_uuid} 用途为 {usage} 的令牌为空")
        return token

    def delete_token(self, player_uuid: str, usage: str) -> bool:
        try:
            keyring.delete_password(self.SERVICE_NAME, f"{usage}@{player_uuid}")
            self.logger.info(f"已删除玩家 UUID {player_uuid} 用途为 {usage} 的令牌")
            return True
        except keyring.errors.PasswordDeleteError:
            self.logger.warning(
                f"在尝试删除玩家 UUID {player_uuid} 用途为 {usage} 的令牌时抛出异常：键名为 {usage}@{player_uuid} 的令牌不存在"
            )
            return False

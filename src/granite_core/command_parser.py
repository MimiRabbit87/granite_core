class Lexer:
    def __init__(self) -> None:
        self.command: str = ""

    def set_command(self, command: str) -> None:
        self.command = command.strip()

    def analyze(self) -> list[str]:
        if not self.command:
            return []

        token_list: list[str] = []
        token: str = ""
        is_in_string: bool = False
        escape_next: bool = False

        for char in self.command:
            if escape_next:
                token += char
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            if char == " " and not is_in_string:
                token_list.append(token)
                token = ""
                continue

            if char == "\"":
                is_in_string = not is_in_string
                token += char
                continue

            token += char
        token_list.append(token)

        return token_list


class CommandParser:
    def __init__(self) -> None:
        self.MAIN_COMMANDS: dict[str, dict[str, dict[str, list[...] | ... | ...] | ...]] = {
            "Create-Task": {
                "function": lambda: ...,
                "args": {
                    "-Type": [
                        {
                            "requirements": {},
                            "provided": "mandatory",
                        }
                    ],
                    "-Version": [
                        {
                            "requirements": {"-Type": "Install-Game"},
                            "provided": "optional",
                        }
                    ],
                    "-AsName": [
                        {
                            "requirements": {"-Type": "Install-Game"},
                            "provided": "optional",
                        }
                    ],
                },
            },
        }
        self.token_list: list[str] = []

    def set_token_list(self, token_list: list[str]) -> None:
        self.token_list = token_list

    def parse(self) -> dict[str, any]:
        if not self.token_list:
            return {"error": "Empty command"}

        if self.token_list[0] not in self.MAIN_COMMANDS:
            return {"error": f"SyntaxError: Invalid command '{self.token_list[0]}'"}

        command_name = self.token_list[0]
        command_info = self.MAIN_COMMANDS[command_name]

        # 解析参数
        args = {}
        current_flag = None
        is_in_string: bool = False

        for token in self.token_list[1:]:
            if token == "\"":
                is_in_string = not is_in_string
                continue

            if token.startswith("-") and not is_in_string:
                if current_flag is not None:
                    args[current_flag] = None

                if token not in command_info["args"]:
                    return {"error": f"SyntaxError: Invalid flag '{token}'"}

                current_flag = token
            else:
                if current_flag is None:
                    return {"error": f"SyntaxError: Unexpected value '{token}' without flag"}

                args[current_flag] = token
                current_flag = None

        if current_flag is not None:
            args[current_flag] = None

        # 验证参数要求
        for flag, conditions in command_info["args"].items():
            mandatory_required = False

            for condition in conditions:
                if condition["provided"] == "mandatory":
                    mandatory_required = True
                    break

            if mandatory_required and flag not in args:
                condition_met = False
                for condition in conditions:
                    if condition["provided"] == "mandatory":
                        req_met = True
                        for req_flag, req_value in condition.get("requirements", {}).items():
                            if req_flag not in args or args[req_flag] != req_value:
                                req_met = False
                                break

                        if req_met:
                            condition_met = True
                            break

                if condition_met and flag not in args:
                    return {"error": f"ArgumentError: Missing mandatory argument '{flag}'"}

        return {
            "error": "",
            "command": command_name,
            "function": command_info["function"],
            "args": args
        }


if __name__ == "__main__":
    lexer: Lexer = Lexer()
    parser: CommandParser = CommandParser()
    while True:
        user_input = input("> ")
        lexer.set_command(user_input)
        analysis: list[str] = lexer.analyze()
        if analysis:
            parser.set_token_list(analysis)
            print(parser.parse())

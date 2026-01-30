import command_parser


class GraniteCommandLine:
    @staticmethod
    def main() -> int:
        lexer: command_parser.Lexer = command_parser.Lexer()
        parser: command_parser.CommandParser = command_parser.CommandParser()

        while True:
            user_input = input("@GraniteLauncher> ")
            if user_input == "Quit-Application":
                return 0
            lexer.set_command(user_input)
            analysis: list[str] = lexer.analyze()
            if analysis:
                parser.set_token_list(analysis)
                parse_result: dict[str, any] = parser.parse()
                if parse_result["error"]:
                    print(parse_result["error"])
                else:
                    if parse_result["command"] == "Create-Task":
                        if parse_result["args"]["-Type"] == "Install-Game":
                            # TODO: Install Minecraft Game
                            ...


if __name__ == "__main__":
    GraniteCommandLine.main()

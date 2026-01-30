import sys

import command_parser
import granite_command_line
import granite_settings
import minecraft_manager
import minecraft_installer
import task_queue


class Main:
    @staticmethod
    def main() -> int:
        if len(sys.argv) > 0:
            if "nogui" in sys.argv:
                granite_command_line.GraniteCommandLine.main()

        return 0


if __name__ == "__main__":
    Main.main()

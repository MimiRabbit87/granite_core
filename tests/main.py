import json
import unittest

import granite_core


class Test(unittest.TestCase):
    def test(self) -> None:
        installer: granite_core.minecraft_installer.MinecraftInstaller = granite_core.minecraft_installer.MinecraftInstaller(
            granite_core.granite_settings.GraniteSettings(),
            "rd-132211",
            "Mojang"
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


if __name__ == "__main__":
    unittest.main()

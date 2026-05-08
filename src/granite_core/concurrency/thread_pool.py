"""
    Thread Pool: just an implement of a thread pool.
    Copyright (C) 2026 MimiRabbit

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from __future__ import annotations

import collections
import logging
import threading
import typing


class ThreadPool:
    def __init__(self, max_workers: int) -> None:
        self.logger: logging.Logger = logging.getLogger("ThreadPool")
        self.max_workers: int = max_workers
        self.threads: list[threading.Thread] = \
            [threading.Thread(target=self._worker, args=(i,)) for i in range(max_workers)]
        self.tasks: collections.deque[tuple[typing.Callable, tuple[typing.Any], dict[str, typing.Any]]] = \
            collections.deque()
        self.running_flag: bool = True
        self.condition: threading.Condition = threading.Condition()

        for thread in self.threads:
            thread.start()

    def _worker(self, worker_id: int) -> None:
        while True:
            with self.condition:
                while not self.tasks and self.running_flag:
                    self.condition.wait()
                if not self.tasks and not self.running_flag:
                    break
                current_task: tuple[typing.Callable, tuple[typing.Any], dict[str, typing.Any]] = self.tasks.popleft()
                (function, arguments, keyword_arguments) = current_task

            try:
                function(*arguments, **keyword_arguments)
            except Exception:  # noqa
                self.logger.exception(
                    f"An error occurred while worker {worker_id} was dealing with a task:"
                )

    def submit(
            self,
            function: typing.Callable,
            arguments: tuple[typing.Any] | None=None,
            keyword_arguments: dict[str, typing.Any] | None=None
    ) -> None:
        if arguments is None:
            arguments = []
        if keyword_arguments is None:
            keyword_arguments = {}

        with self.condition:
            self.tasks.append((function, arguments, keyword_arguments))
            self.condition.notify()

    def shutdown(self, force: bool=False) -> None:
        with self.condition:
            if force:
                self.tasks.clear()
            self.running_flag = False
            self.condition.notify_all()

        for worker in self.threads:
            worker.join()

"""
    Task Queue: just an implement of a task queue.
    Copyright (C) 2026 MimiRabbit

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    这个任务队列太好用了你知道吗
"""

from __future__ import annotations

import concurrent.futures
import heapq
import threading
import time
import traceback
import typing


class TaskQueue:
    max_workers: int
    __original_tasks: list
    tasks: list
    pending_tasks: list
    task_counter: int
    runnable_tasks: dict[int, dict]
    thread_pool: concurrent.futures.ThreadPoolExecutor
    stop_flag: bool = False
    idle_threads: list[int]
    __results: dict[str, typing.Any]
    condition: threading.Condition

    def __init__(self, max_workers: int, thread_pool_: concurrent.futures.ThreadPoolExecutor) -> None:
        self.max_workers = max_workers
        self.__original_tasks = []
        self.tasks = []  # 最小堆，存储 (-priority, task_id, task)
        self.pending_tasks = []  # 也是一堆
        self.task_counter = 0
        self.runnable_tasks = {}
        self.thread_pool = thread_pool_
        self.stop_flag = False
        self.idle_threads = list(range(max_workers))
        self.__results = {}
        self.condition = threading.Condition()  # This is a condition

    def submit(self, task: dict[str, typing.Any]) -> None:
        """
        Task format:
        {
            "id": id,
            "description": description,
            "function": function to be executed,
            "args": args,
            "kwargs": kwargs,
            "callback": callback function,
            "callback_args": callback args,
            "callback_kwargs": callback kwargs,
            "max_time": max time (seconds),
            "max_retries": max retries, -1 = infinite,
            "pre_tasks": pre-task list (task ids),
            "priority": priority (higher number = higher priority)
        }
        :param task: Task to be added
        :return: None
        """
        # task 也要初始化
        task["id"] = str(task["id"])
        if "pre_tasks" in task:
            task["pre_tasks"] = [str(t) for t in task["pre_tasks"]]

        with self.condition:
            if task.get("pre_tasks"):  # Check if this task includes pre-tasks，然后什么什么 blabla 的
                priority = task.get("priority", 0)
                heapq.heappush(self.pending_tasks, (-priority, self.task_counter, task))
                self.task_counter += 1
                self.condition.notify()
            else:
                # 优先级默认为 0
                priority = task.get("priority", 0)
                heapq.heappush(self.tasks, (-priority, self.task_counter, task))
                heapq.heappush(self.__original_tasks, (-priority, self.task_counter, task))
                self.task_counter += 1
                self.condition.notify()

    def restart_task(self, task_id: str) -> None:
        """Restart a task in original_tasks"""
        for i, task in enumerate(self.__original_tasks.copy()):
            if task[2]["id"] == task_id:
                edited_task: dict = task[2]
                edited_task["priority"] = -task[0]
                del self.original_tasks[i]
                self.submit(edited_task)

    def run(self) -> None:
        """The main running loop, assigning tasks to idle threads"""
        self.thread_pool.submit(self.check_pre_tasks)

        while not self.stop_flag:
            with self.condition:
                if not self.idle_threads or not self.tasks:
                    if (not self.tasks and
                            not self.runnable_tasks and
                            not self.pending_tasks and
                            len(self.idle_threads) == self.max_workers
                    ):  # 究极 shutdown 条件
                        break
                    self.condition.wait(1)
                    continue

                # 获取优先级最高的任务
                if self.tasks:
                    _, _, task = heapq.heappop(self.tasks)
                    if self.idle_threads:
                        thread_id = self.idle_threads.pop(0)
                        self.thread_pool.submit(self.run_runnable_task, thread_id)
                        self.runnable_tasks[thread_id] = task
                        self.condition.notify_all()

            # print(self.idle_threads)  # 测试用的这玩意

    def check_pre_tasks(self) -> None:
        while not self.stop_flag:
            ready_tasks = []
            with self.condition:
                if not self.pending_tasks:
                    self.condition.wait()
                    continue

                to_remove = []
                for i, (priority, counter, task) in enumerate(self.pending_tasks):
                    if set(task["pre_tasks"]).issubset(self.__results.keys()):
                        ready_tasks.append((priority, counter, task))
                        to_remove.append(i)

                for i in reversed(to_remove):
                    self.pending_tasks.pop(i)

                if ready_tasks:
                    for task_tuple in ready_tasks:
                        heapq.heappush(self.tasks, task_tuple)
                    self.condition.notify_all()
                    continue

            time.sleep(0.1)

    def run_runnable_task(self, thread_id: int) -> None:
        """线程执行任务的函数"""
        while not self.stop_flag:
            with self.condition:
                if thread_id not in self.runnable_tasks:
                    if thread_id not in self.idle_threads:
                        self.idle_threads.append(thread_id)
                    break

                task = self.runnable_tasks[thread_id]
                del self.runnable_tasks[thread_id]

            while True:
                for _ in range(task.get("max_retries", 0) + 1):
                    try:
                        result = task["function"](*task.get("args", ()), **task.get("kwargs", {}))
                        with self.condition:
                            self.__results[task["id"]] = result
                        break
                    except Exception as e:
                        if _ == task.get("max_retries", 0):
                            with self.condition:
                                self.__results[task["id"]] = traceback.format_exception(Exception, e, e.__traceback__)

                if task.get("max_retries", 0) != -1:  # 这个地方添柴（sb）设计有没有
                    break  # 不想动了

            if task.get("callback", 0):
                task["callback"](*task.get("callback_args", ()), **task.get("callback_kwargs", {}))

            with self.condition:
                self.idle_threads.append(thread_id)
                self.condition.notify()

    def wait(self) -> None:
        with self.condition:
            if self.stop_flag:
                return
            else:
                self.condition.wait()

    def shutdown(self) -> None:
        """Stop the task queue, clearing all tasks"""
        self.stop_flag = True
        with self.condition:
            self.tasks = []
            self.runnable_tasks = {}
            self.condition.notify_all()

    @property
    def results(self) -> dict[str, typing.Any]:
        with self.condition:
            return self.__results.copy()

    @results.setter
    def results(self, value: dict[str, typing.Any]) -> None:
        self.__results = value

    def delete_result(self, task_id: str) -> None:
        with self.condition:
            del self.__results[task_id]

    @property
    def original_tasks(self) -> list:
        with self.condition:
            return self.__original_tasks.copy()

    @original_tasks.setter
    def original_tasks(self, value: list) -> None:
        self.__original_tasks = value

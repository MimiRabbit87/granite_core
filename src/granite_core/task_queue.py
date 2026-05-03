"""
    这个任务队列太好用了你知道吗
"""

from __future__ import annotations

import heapq
import threading
import traceback
import typing

from . import thread_pool


class TaskQueue:
    def __init__(self, max_workers: int, thread_pool_: thread_pool.ThreadPool) -> None:
        self.max_workers: int = max_workers
        self.__original_tasks: list = []
        self.tasks: list = []  # 最小堆，存储 (-priority, task_id, task)
        self.pending_tasks: list = []  # 也是一堆
        self.task_counter: int = 0
        self.runnable_tasks: dict[int, dict] = {}
        self.thread_pool: thread_pool.ThreadPool = thread_pool_
        self.stop_flag: bool = False
        self.lock: threading.Lock = threading.Lock()  # This is a lock
        self.idle_threads: list[int] = list(range(max_workers))
        self.__results: dict[str, typing.Any] = {}
        self.condition: threading.Condition = threading.Condition(self.lock)  # And this is a condition

    def add_task(self, task: dict[str, typing.Any]) -> None:
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

        with self.lock:
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
                self.add_task(edited_task)

    def run(self) -> None:
        """The main running loop, assigning tasks to idle threads"""
        self.thread_pool.submit(self.check_pre_tasks)

        while not self.stop_flag:
            with self.lock:
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
                        self.thread_pool.submit(self.run_runnable_task, (thread_id,))
                        self.runnable_tasks[thread_id] = task
                        self.condition.notify_all()

            # print(self.idle_threads)  # 测试用的这玩意

    def check_pre_tasks(self) -> None:
        ready_tasks = []
        while not self.stop_flag:
            with self.condition:
                if ready_tasks:
                    for task in ready_tasks:
                        heapq.heappush(self.tasks, task)

                    ready_tasks = []

                if not self.pending_tasks:
                    self.condition.wait()

                # 遍历等待任务，看看 if 任务的前置执行完毕（看起来思路很 l，实则实现也是）
                for i in range(len(self.pending_tasks)):
                    priority, task_counter, task = self.pending_tasks[i]

                    pre_tasks_set = set(task["pre_tasks"])
                    results_keys = set(self.__results.keys())
                    if pre_tasks_set.issubset(results_keys):
                        ready_tasks.append((priority, task_counter, task))
                        self.pending_tasks.pop(i)
                        break

    def run_runnable_task(self, thread_id: int) -> None:
        """线程执行任务的函数"""
        while not self.stop_flag:
            with self.lock:
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
                        with self.lock:
                            self.__results[task["id"]] = result
                        break
                    except Exception as e:
                        if _ == task.get("max_retries", 0):
                            with self.lock:
                                self.__results[task["id"]] = traceback.format_exception(Exception, e, e.__traceback__)

                if task.get("max_retries", 0) != -1:  # 这个地方添柴（sb）设计有没有
                    break  # 不想动了

            if task.get("callback", 0):
                task["callback"](*task.get("callback_args", ()), **task.get("callback_kwargs", {}))

            with self.lock:
                self.idle_threads.append(thread_id)
                self.condition.notify()

    def shutdown(self) -> None:
        """Stop the task queue, clearing all tasks"""
        self.stop_flag = True
        with self.lock:
            self.tasks = []
            self.runnable_tasks = {}
            self.condition.notify_all()

    @property
    def results(self) -> dict[str, typing.Any]:
        with self.lock:
            return self.__results.copy()

    @results.setter
    def results(self, value: dict[str, typing.Any]) -> None:
        self.__results = value

    def delete_result(self, task_id: str) -> None:
        with self.lock:
            del self.__results[task_id]

    @property
    def original_tasks(self) -> list:
        with self.lock:
            return self.__original_tasks.copy()

    @original_tasks.setter
    def original_tasks(self, value: list) -> None:
        self.__original_tasks = value

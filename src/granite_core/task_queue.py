"""
    这个任务队列太好用了你知道吗
"""

import threading
import heapq
import time


class TaskQueue:
    def __init__(self, max_workers: int) -> None:
        self.max_workers: int = max_workers
        self.tasks = []  # 最小堆，存储 (-priority, task_id, task)
        self.pending_tasks = []  # 也是一堆
        self.task_counter = 0
        self.runnable_tasks: dict[int, dict] = {}
        self.thread_pool = [threading.Thread(target=self.run_runnable_task, args=(i,)) for i in range(max_workers)]
        self.stop_flag: bool = False
        self.lock: threading.Lock = threading.Lock()  # This is a lock
        self.free_threads: list[int] = list(range(max_workers))
        self.results: dict[str, any] = {}
        self.condition = threading.Condition(self.lock)  # And this is a condition
        for t in self.thread_pool:
            t.start()

    def add_task(self, task: dict[str, any]) -> None:
        """
        Task format:
        {
            "id": id,
            "description": description,
            "function": function to be executed (Perhaps it's been deprecated),
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
                self.task_counter += 1
                self.condition.notify()

    def run(self) -> None:
        """主运行循环，将任务分配给空闲线程"""
        pre_task_thread: threading.Thread = threading.Thread(target=self.check_pre_tasks)
        pre_task_thread.start()

        while not self.stop_flag:
            with self.lock:
                if not self.free_threads or not self.tasks:
                    if (not self.tasks and
                            not self.runnable_tasks and
                            not self.pending_tasks and
                            len(self.free_threads) == len(self.thread_pool)
                    ):  # 究极 shutdown 条件
                        break
                    self.condition.wait(1)
                    continue

                # 获取优先级最高的任务
                if self.tasks:
                    _, _, task = heapq.heappop(self.tasks)
                    if self.free_threads:
                        thread_id = self.free_threads.pop(0)
                        self.runnable_tasks[thread_id] = task
                        self.condition.notify_all()

            # print(self.free_threads)  # 测试用的这玩意

    def check_pre_tasks(self) -> None:
        ready_tasks = []
        while not self.stop_flag:
            with self.lock:
                if ready_tasks:
                    for task in ready_tasks:
                        heapq.heappush(self.tasks, task)

                    ready_tasks = []

                if not self.pending_tasks:
                    break

                # 遍历等待任务，看看 if 任务的前置执行完毕（看起来思路很 l，实则实现也是）
                for i in range(len(self.pending_tasks)):
                    priority, task_counter, task = self.pending_tasks[i]

                    pre_tasks_set = set(task["pre_tasks"])
                    results_keys = set(self.results.keys())
                    if pre_tasks_set.issubset(results_keys):
                        ready_tasks.append((priority, task_counter, task))
                        self.pending_tasks.pop(i)
                        break

    def run_runnable_task(self, thread_id: int) -> None:
        """线程执行任务的函数"""
        while not self.stop_flag:
            with self.lock:
                if thread_id not in self.runnable_tasks:
                    if thread_id not in self.free_threads:
                        self.free_threads.append(thread_id)
                    self.condition.wait()
                    continue

                task = self.runnable_tasks[thread_id]
                del self.runnable_tasks[thread_id]

            while True:
                for _ in range(task.get("max_retries", 0) + 1):
                    try:
                        result = task["function"](*task.get("args", ()), **task.get("kwargs", {}))
                        with self.lock:
                            self.results[task["id"]] = result
                        break
                    except Exception as e:
                        if _ == task.get("max_retries", 0):
                            with self.lock:
                                self.results[task["id"]] = f"Error: {str(e)}"

                if task.get("max_retries", 0) != -1:  # 这个地方添柴（sb）设计有没有
                    break  # 不想动了

            if task.get("callback", 0):
                task["callback"](*task.get("callback_args", ()), **task.get("callback_kwargs", {}))

            with self.lock:
                self.free_threads.append(thread_id)
                self.condition.notify()

    def shutdown(self) -> None:  # 停机
        self.stop_flag = True
        with self.lock:
            self.condition.notify_all()
        for thread in self.thread_pool:
            thread.join()

    def get_results(self) -> dict[str, any]:  # 拿结果
        with self.lock:
            return self.results.copy()


if __name__ == "__main__":
    # test
    def example_task(name, duration=1):
        """示例任务函数"""
        print(f"任务 {name} 开始执行，预计耗时 {duration}s")
        time.sleep(duration)
        result = f"任务 {name} 完成 in {duration}s"
        print(result)
        return result


    # 创建任务队列
    task_queue = TaskQueue(max_workers=3)

    # also test
    # 优先级越高，优先级越高（？）
    task_queue.add_task({
        "id": "0",
        "description": "低优先级任务",
        "function": example_task,
        "args": ("低优先级", 3),
        "priority": 1  # 低优先级
    })

    task_queue.add_task({
        "id": "1",
        "description": "中优先级任务",
        "function": example_task,
        "args": ("中优先级", 2),
        "priority": 5  # 中优先级
    })

    task_queue.add_task({
        "id": "2",
        "description": "高优先级任务",
        "function": example_task,
        "args": ("高优先级", 1),
        "priority": 10  # 高优先级
    })

    task_queue.add_task({
        "id": "3",
        "description": "带有前置任务的高优先级任务",
        "function": example_task,
        "args": ("带有前置任务的高优先级", 1),
        "pre_tasks": [0],  # 前置
        "priority": 10  # 高优先级
    })

    task_queue.add_task({
        "id": "4",
        "description": "高优先级任务",
        "function": task_queue.add_task,
        "args": ({
                "id": 5,
                "description": "带有前置任务的高优先级任务",
                "function": example_task,
                "args": ("带有前置任务的高优先级", 1),
                "pre_tasks": [0],  # 前置
                "priority": 10  # 高优先级
        },),
        "priority": 10  # 高优先级
    })

    # 启动任务队列
    task_queue.run()
    task_queue.shutdown()

    # 获取结果
    results = task_queue.get_results()
    print("任务结果:", results)

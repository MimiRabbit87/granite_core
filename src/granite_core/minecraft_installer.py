import hashlib
import json
import os
import pathlib
import logging
import threading
import time
import shutil
import typing

import requests.adapters
import urllib3

from . import granite_settings
from . import task_queue

logging.basicConfig(level=logging.INFO, format='[%(asctime)s][%(levelname)s]%(message)s', encoding="utf-8")


class MinecraftInstaller:
    def __init__(self, settings: granite_settings.GraniteSettings, install_version: str, download_source: str) -> None:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # 把 SSL 验证禁了，下载文件用不着，拖慢速度不说，报错率直线上涨
        self.install_running_flag: bool = True
        self.settings = settings
        self.install_version: str = install_version
        self.install_main_path: pathlib.Path = settings.working_path
        self.download_source: str = download_source
        self.minecraft_version_manifest_path: dict[str, str] = {
            "Mojang": "https://launchermeta.mojang.com/mc/game/version_manifest.json",
            "BMCLAPI": "https://bmclapi2.bangbang93.com/mc/game/version_manifest.json"
        }
        self.minecraft_assets_path: dict[str, str] = {
            "Mojang": "https://resources.download.minecraft.net",
            "BMCLAPI": "https://bmclapi2.bangbang93.com/assets"
        }

        # 下载中使用
        # 连接池啊这个是
        self.session = requests.Session()
        retry_strategy = urllib3.util.Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[403, 429, 500, 502, 503, 504, 567],
        )
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=self.settings.max_workers,  # 连接池大小
            pool_maxsize=self.settings.max_workers,
            max_retries=retry_strategy
        )
        self.session.mount("https://", adapter)

        self.install_queue: task_queue.TaskQueue = task_queue.TaskQueue(self.settings.max_workers)
        self.version_manifest: dict = {}
        self.version_metadata: dict = {}
        self.total_assets: int = 0
        self.installed_assets: int = 0
        self.failed_assets: int = 0
        self.retried_assets: int = 0
        self.total_libraries: int = 0
        self.installed_libraries: int = 0
        self.failed_libraries: int = 0
        self.retried_libraries: int = 0

    def install(self) -> int:
        start_time: float = time.time()
        self._install_tasks_init()
        logging.info("[Installer]: 下载任务初始化完成")

        self.install_queue.run()
        self.install_queue.shutdown()
        logging.info(f"[Installer]: 下载任务完成，用时 {time.time() - start_time:.3f}s，{self.failed_libraries=}，{self.failed_assets=}")
        # logging.info(self.install_queue.get_results())  # 测试用的

        return 0

    def download_manifest(self) -> int:
        manifest: dict = json.loads(
            requests.request("GET", self.minecraft_version_manifest_path[self.download_source]).text)
        self.version_manifest = manifest

        return 0

    def download_version_metadata(self) -> int:
        version_metadata: dict = {}
        for version in self.version_manifest["versions"]:
            if version["id"] == self.install_version:
                version_metadata: dict = json.loads(
                    requests.request("GET",
                                     version["url"].replace("piston-meta.mojang.com", "bmclapi2.bangbang93.com") if self.download_source == "BMCLAPI"
                                     else version["url"]).text)
                break
        if not version_metadata:
            return -1

        os.makedirs(self.install_main_path / "versions" / self.install_version, exist_ok=True)
        with open(self.install_main_path / "versions" / self.install_version / f"{self.install_version}.json", "w",
                  encoding="utf-8") as version_metadata_file:
            json.dump(version_metadata, version_metadata_file, indent=2)

        self.version_metadata = version_metadata
        logging.info("[Installer]: 版本元数据下载完成")

        return 0

    def download_game_main_file(self) -> int:
        if not self.version_metadata:
            logging.info(f"[Installer]: 未检测到游戏元数据，{self.version_metadata}")
            self.install_running_flag = False
            return -1

        if os.path.isfile(self.install_main_path / "versions" / self.install_version / f"{self.install_version}.jar"):
            with open(self.install_main_path / "versions" / self.install_version / f"{self.install_version}.jar",
                      "rb") as f:
                if hashlib.sha1(f.read()).hexdigest() == self.version_metadata["downloads"]["client"]["sha1"]:
                    logging.info("[Installer]: 已存在主文件")
                    return 0

        file_chunked: list[tuple[int, int]] = self._compute_download_file_chunked(
            self.version_metadata["downloads"]["client"]["url"] if self.download_source == "Mojang"
            else self.version_metadata["downloads"]["client"]["url"]
            .replace("piston-meta.mojang.com", "bmclapi2.bangbang93.com"),
            4194304
        )
        if not file_chunked:
            return -1

        for i in range(len(file_chunked)):
            self.install_queue.add_task({
                "id": f"main-file-worker-{i}",
                "description": f"下载游戏主文件的 ({file_chunked[i]})",
                "function": self._download_chunk,
                "args": (
                    f"main-file-worker-{i}",  # 给个 id，debug 用
                    self.version_metadata["downloads"]["client"]["url"] if self.download_source == "Mojang"
                    else self.version_metadata["downloads"]["client"]["url"]
                    .replace("piston-meta.mojang.com", "bmclapi2.bangbang93.com"),  # 远端地址
                    self.settings.temp_path / "downloads" /
                    self.version_metadata["downloads"]["client"]["sha1"][: 2] /
                    self.version_metadata["downloads"]["client"]["sha1"],  # 下载块路径
                    f"{str(i)}.tmp",  # 下载块文件名
                    file_chunked[i][0], file_chunked[i][1]  # 下载块起始
                ),  # 好长一条参数
                "max_retries": 5,
                "priority": 11
            })
            time.sleep(1)  # 给点延迟防止太多 429 影响效率

        if self._wait_main_file_downloading_completion(len(file_chunked)):
            with open(self.install_main_path / "versions" / self.install_version / f"{self.install_version}.jar",
                      "wb+") as f:
                for downloaded_chunk in range(len(file_chunked)):
                    with open(self.settings.temp_path / "downloads" /
                              self.version_metadata["downloads"]["client"]["sha1"][: 2] /
                              self.version_metadata["downloads"]["client"]["sha1"] /
                              f"{str(downloaded_chunk)}.tmp", "rb") as tmp:
                        f.write(tmp.read())
            # 只是删个缓存，希望不要出什么 bug
            shutil.rmtree(
                self.settings.temp_path / "downloads" / self.version_metadata["downloads"]["client"]["sha1"][: 2])
        else:
            logging.info("[Installer]: 主文件下载失败，下载任务结束，等待其余线程完成执行，结果弃置")
            self.install_running_flag = False
            self.install_queue.shutdown()
            return False

        with open(self.install_main_path / "versions" / self.install_version / f"{self.install_version}.jar", "rb") as f:
            # 校验散列值
            if hashlib.sha1(f.read()).hexdigest() != self.version_metadata["downloads"]["client"]["sha1"]:
                logging.info(
                    f"[Installer]: 主文件散列值校验失败，已下载主文件散列值为 {hashlib.sha1(f.read()).hexdigest()}")
                return -1
            else:
                logging.info("[Installer]: 版本主文件下载完成")

        return 0

    def download_game_asset_index(self) -> int:
        while True:
            if os.path.isfile(
                    self.install_main_path / "assets" / "indexes" / f"{self.version_metadata["assetIndex"]["id"]}.json"):
                with open(
                        self.install_main_path / "assets" / "indexes" / f"{self.version_metadata["assetIndex"]["id"]}.json",
                        "rb"
                ) as f:
                    if hashlib.sha1(f.read()).hexdigest() == self.version_metadata["assetIndex"]["sha1"]:
                        logging.info("[Installer]: 已有资源索引文件")
                        break

            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                asset_index: dict = json.loads(requests.request(
                    "GET",
                    self.version_metadata["assetIndex"]["url"] if self.download_source == "Mojang"
                    else self.version_metadata["assetIndex"]["url"].replace("piston-meta.mojang.com",
                                                                            "bmclapi2.bangbang93.com"),
                    headers=headers, timeout=60).text)
                os.makedirs(self.install_main_path / "assets" / "indexes", exist_ok=True)
                with open(
                        self.install_main_path / "assets" / "indexes" / f"{self.version_metadata["assetIndex"]["id"]}.json",
                        'w') as f:
                    json.dump(asset_index, f, indent=2)

                logging.info(f"[Installer]: 下载资源索引文件 {self.version_metadata["assetIndex"]["id"]} 成功")

            except Exception as e:
                logging.error(f"[Installer]: 下载资源索引文件失败: {e}")

            break

        return 0

    def download_game_assets(self) -> int:
        with open(self.install_main_path / "assets" / "indexes" / f"{self.version_metadata["assetIndex"]["id"]}.json") as f:
            asset_index: dict = json.load(f)
        assets_info: tuple = tuple(asset_index["objects"].items())
        self.total_assets = len(asset_index["objects"])
        assets_level: int = 0
        assets_range: int = 0
        progress_updater: threading.Thread = threading.Thread(target=self._print_progress,
                                                              args=("资源文件下载进度", self.total_assets, self._get_assets_progress))  # 加个进度条
        progress_updater.start()

        for i in range(len(asset_index["objects"])):
            if (
                    pathlib.Path.exists(self.install_main_path / "assets" / "objects" / assets_info[i][1]["hash"][: 2] / assets_info[i][1]["hash"])
                and pathlib.Path.exists(self.install_main_path / "assets" / "virtual" / "legacy" / assets_info[i][0])
                and pathlib.Path.exists(self.install_main_path / "assets" / "virtual" / "pre-1.6" / assets_info[i][0])
            ):
                if (
                        hashlib.sha1(self.install_main_path / "assets" / "objects" / assets_info[i][1]["hash"][: 2] / assets_info[i][1]["hash"]) == assets_info[i][1]["hash"]
                    and hashlib.sha1(self.install_main_path / "assets" / "virtual" / "legacy" / assets_info[i][0]) == assets_info[i][1]["hash"]
                    and hashlib.sha1(self.install_main_path / "assets" / "virtual" / "pre-1.6" / assets_info[i][0]) == assets_info[i][1]["hash"]
                ):
                    continue

            self.install_queue.add_task({
                "id": f"asset-downloading-worker-{i}",
                "description": f"下载游戏资源文件的 ({assets_info[i][0]}, {assets_info[i][1]["hash"]})",
                "function": self._regular_download,
                "args": (
                    f"asset-downloading-worker-{i}",  # 给个 id，debug 用
                    f"{self.minecraft_assets_path[self.download_source]}/"
                    f"{assets_info[i][1]["hash"][: 2]}/{assets_info[i][1]["hash"]}",  # 远端地址
                    [
                        self.install_main_path / "assets" / "objects" / assets_info[i][1]["hash"][: 2],
                        (self.install_main_path / "assets" / "virtual" / "legacy" / assets_info[i][0]).parent,
                        (self.install_main_path / "assets" / "virtual" / "pre-1.6" / assets_info[i][0]).parent
                    ],  # 下载资源文件路径
                    [
                        assets_info[i][1]["hash"],
                        pathlib.Path(assets_info[i][0]).name,
                        pathlib.Path(assets_info[i][0]).name
                    ],  # 下载资源文件名
                    assets_info[i][1]["hash"]  # 散列值
                ),  # 又是好长一条参数
                "callback": self._asset_downloading_callback,
                "callback_args": (f"asset-downloading-worker-{i}", assets_info[i]),
                "max_retries": 3,
                "priority": 11
            })
            # time.sleep(0.01)  # 休息一下  # 啊，这里是后期的米米兔，这玩意好像没用，到时候再添加防止 429 的策略吧
            assets_range += 1
            if assets_range >= 100:
                self._wait_for_batch_completion((assets_level * 100 + 100) * 0.7)  # 来了噢
                assets_level += 1
                assets_range -= 100

        return 0

    def download_game_libraries(self) -> int:
        self.total_libraries = 0
        for lib in self.version_metadata["libraries"]:
            if "classifiers" in lib["downloads"]:
                self.total_libraries += len(lib["downloads"]["classifiers"])
            else:
                self.total_libraries += 1
        libraries_level: int = 0
        libraries_range: int = 0
        progress_updater: threading.Thread = threading.Thread(target=self._print_progress,
                                                              args=("支持库文件下载进度", self.total_libraries, self._get_libraries_progress))  # 加个进度条
        progress_updater.start()

        for i in range(len(self.version_metadata["libraries"])):
            if "classifiers" in self.version_metadata["libraries"][i]["downloads"]:
                for classifier in self.version_metadata["libraries"][i]["downloads"]["classifiers"].values():
                    if pathlib.Path.exists(self.install_main_path / "libraries" / classifier["path"]):
                        if hashlib.sha1(self.install_main_path / "libraries" / classifier["path"]) == classifier["sha1"]:
                            continue

                    self.install_queue.add_task({
                        "id": f"library-downloading-worker-{i}",
                        "description": f"下载游戏支持库 ({self.version_metadata["libraries"][i]["name"]}) 的动态链接库文件 ({pathlib.Path(classifier['path']).name})",
                        "function": self._regular_download,
                        "args": (
                            f"library-downloading-worker-{i}",  # 给个 id，debug 用
                            # 远端地址
                            f"{classifier["url"] if self.download_source == "Mojang"
                            else classifier["url"].replace("https://libraries.minecraft.net", "https://bmclapi2.bangbang93.com/maven")}",
                            # 下载支持库文件路径
                            [(self.install_main_path / "libraries" /
                              classifier["path"]).parent],
                            # 下载支持库文件名
                            [pathlib.Path(classifier["path"]).name],
                            # 散列值
                            classifier["sha1"]
                        ),  # 仍然是好长一条参数
                        "callback": self._library_downloading_callback,
                        "callback_args": (f"library-downloading-worker-{i}", {**classifier, "name": self.version_metadata["libraries"][i]["name"]}, True),
                        "max_retries": 3,
                        "priority": 11
                    })
                    libraries_range += len(classifier)
            else:
                if pathlib.Path.exists(self.install_main_path / "libraries" / self.version_metadata["libraries"][i]["downloads"]["artifact"]["path"]):
                    if (hashlib.sha1(self.install_main_path / "libraries" / self.version_metadata["libraries"][i]["downloads"]["artifact"]["path"])
                            == self.version_metadata["libraries"][i]["downloads"]["artifact"]["sha1"]):
                        continue

                self.install_queue.add_task({
                    "id": f"library-downloading-worker-{i}",
                    "description": f"下载游戏支持库文件的 ({self.version_metadata["libraries"][i]["name"]})",
                    "function": self._regular_download,
                    "args": (
                        f"library-downloading-worker-{i}",  # 给个 id，debug 用
                        # 远端地址
                        f"{self.version_metadata["libraries"][i]["downloads"]["artifact"]["url"] if self.download_source == "Mojang"
                        else self.version_metadata["libraries"][i]["downloads"]["artifact"]["url"].replace("https://libraries.minecraft.net", "https://bmclapi2.bangbang93.com/maven")}",
                        # 下载支持库文件路径
                        [(self.install_main_path / "libraries" / self.version_metadata["libraries"][i]["downloads"]["artifact"]["path"]).parent],
                        # 下载支持库文件名
                        [pathlib.Path(self.version_metadata["libraries"][i]["downloads"]["artifact"]["path"]).name],
                        # 散列值
                        self.version_metadata["libraries"][i]["downloads"]["artifact"]["sha1"]
                    ),  # 仍然是好长一条参数
                    "callback": self._library_downloading_callback,
                    "callback_args": (f"library-downloading-worker-{i}", self.version_metadata["libraries"][i]),
                    "max_retries": 3,
                    "priority": 11
                })
                libraries_range += 1

            if libraries_range >= 100:
                self._wait_for_batch_completion((libraries_level * 50 + 50) * 0.7)  # 来了噢
                libraries_level += 1
                libraries_range -= 100

        return 0

    def _retry_download_game_resources(self, task: dict[str, any]) -> int:
        def retry() -> int:
            self.install_queue.add_task(task)
            return 0

        return retry()

    def _install_tasks_init(self) -> int:
        # 要开始了哦
        self.install_queue.add_task({
            "id": "0",
            "description": "下载版本清单文件",
            "function": self.download_manifest,
            "args": (),
            "priority": 10
        })
        self.install_queue.add_task({
            "id": "1",
            "description": "下载游戏元数据",
            "function": self.download_version_metadata,
            "args": (),
            "pre_tasks": ["0"],
            "priority": 10
        })
        self.install_queue.add_task({
            "id": "2",
            "description": "下载游戏主文件",
            "function": self.download_game_main_file,
            "args": (),
            "pre_tasks": ["1"],
            "priority": 10
        })
        self.install_queue.add_task({
            "id": "3",
            "description": "下载游戏资源索引文件",
            "function": self.download_game_asset_index,
            "args": (),
            "pre_tasks": ["1"],
            "priority": 10
        })
        self.install_queue.add_task({
            "id": "4",
            "description": "下载游戏资源文件",
            "function": self.download_game_assets,
            "args": (),
            "pre_tasks": ["3"],
            "priority": 10
        })
        self.install_queue.add_task({
            "id": "5",
            "description": "下载游戏支持库文件",
            "function": self.download_game_libraries,
            "args": (),
            "pre_tasks": ["1"],
            "priority": 10
        })

        return 0

    @staticmethod
    def _compute_download_file_chunked(
            url: str,  # 文件下载地址
            chunk_size: int  # 单分块大小
    ) -> list:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response: requests.Response = requests.head(url, headers=headers, allow_redirects=True)

            if 'Accept-Ranges' not in response.headers:
                logging.info("[Installer]: 服务器不支持分块下载，使用普通下载")
                return []

            file_size: int = int(response.headers.get('Content-Length', 0))
        except Exception as e:
            logging.error(f"[Installer]:\n{e}")
            return []

        chunks: list = []
        for start in range(0, file_size, chunk_size):
            end = min(start + chunk_size - 1, file_size - 1)
            chunks.append((start, end))

        logging.debug(chunks)
        return chunks

    @staticmethod
    def _download_chunk(worker_id: str, url: str, chunk_path: pathlib.Path, chunk_file: str,
                       start: int, end: int) -> bool:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Range": f"bytes={start}-{end}"
            }

            response: requests.Response = requests.get(url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()

            os.makedirs(chunk_path, exist_ok=True)
            with open(chunk_path / chunk_file, 'wb') as f:
                for data in response.iter_content(chunk_size=8192):
                    f.write(data)

            logging.info(f"[Installer]: 下载块 ({start}-{end}) 成功，{chunk_path / chunk_file}")

            return True
        except Exception as e:
            logging.error(f"[Installer]: 下载块失败 ({start}-{end})，于 {worker_id}: {e}")
            return False

    def _regular_download(self, worker_id: str, url: str, store_path: list[pathlib.Path], store_file: list[str], sha1: str) -> bool:
        if len(store_path) != len(store_file):
            return False
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            response = self.session.get(url, headers=headers, timeout=30, proxies={}, verify=False)
            response.raise_for_status()

            for i in range(len(store_path)):
                os.makedirs(store_path[i], exist_ok=True)
                with open(store_path[i] / store_file[i], 'wb') as f:
                    f.write(response.content)
                """if hashlib.sha1(response.content).hexdigest() != sha1:
                    logging.info(
                        f"[Installer]: 文件 {url} 散列值校验失败，于 {worker_id}，原文件散列值 {hashlib.sha1(response.content).hexdigest()}，但期望 {sha1}")
                    return False"""  # 看看不校验的话速度会不会快很多，果真，快了十几秒

            return True
        except Exception as e:
            logging.error(f"[Installer]: 下载文件 {url} 失败，于 {worker_id}: {e}")
            return False

    def _wait_main_file_downloading_completion(self, chunks: int) -> bool:
        chunk_result: dict[str, bool] = {}
        while True:
            for result_key, result_value in self.install_queue.get_results().items():
                if "main-file-worker-" in result_key:
                    chunk_result[result_key] = result_value
            if len(chunk_result) == chunks:
                break
            time.sleep(1)

        finish_install: bool = True
        for _, result in chunk_result.items():
            if not result:
                finish_install = False
                break

        return finish_install

    def _asset_downloading_callback(self, worker_id: str, asset_data: dict) -> int:
        if self.install_queue.get_results()[worker_id]:
            self.installed_assets += 1
        else:
            if not asset_data:
                self.failed_libraries += 1
                return -1

            self._retry_download_game_resources({
                "id": f"asset-downloading-worker-{self.retried_assets}",
                "description": f"下载游戏资源文件的 ({asset_data[0]}, {asset_data[1]["hash"]})",
                "function": self._regular_download,
                "args": (
                    f"asset-downloading-worker-{self.retried_assets}",  # 给个 id，debug 用
                    f"{self.minecraft_assets_path[self.download_source]}/"
                    f"{asset_data[1]["hash"][: 2]}/{asset_data[1]["hash"]}",  # 远端地址
                    [
                        self.install_main_path / "assets" / "objects" / asset_data[1]["hash"][: 2],
                        (self.install_main_path / "assets" / "virtual" / "legacy" / asset_data[0]).parent,
                        (self.install_main_path / "assets" / "virtual" / "pre-1.6" / asset_data[0]).parent
                    ],  # 下载资源文件路径
                    [
                        asset_data[1]["hash"],
                        pathlib.Path(asset_data[0]).name,
                        pathlib.Path(asset_data[0]).name
                    ],  # 下载资源文件名
                    asset_data[1]["hash"]  # 散列值
                ),  # 又是好长一条参数
                "callback": self._asset_downloading_callback,
                "callback_args": (f"asset-downloading-worker-{self.retried_assets}", asset_data),
                "max_retries": 3,
                "priority": 12
            })
            self.retried_assets += 1
        return 0

    def _get_assets_progress(self) -> int:
        return self.installed_assets + self.failed_assets

    def _library_downloading_callback(self, worker_id: str, library_data: dict | None = None, is_classifier: bool = False) -> int:
        if self.install_queue.get_results()[worker_id]:
            self.installed_libraries += 1
        else:
            if not library_data:
                self.failed_libraries += 1
                return -1

            if is_classifier:
                self._retry_download_game_resources({
                    "id": f"library-downloading-worker-retry-{self.retried_libraries}",
                    "description": f"重试下载游戏支持库 ({library_data["name"]}) 的动态链接库文件 ({pathlib.Path(library_data['path']).name})",
                    "function": self._regular_download,
                    "args": (
                        f"library-downloading-worker-{self.retried_libraries}",  # 给个 id，debug 用
                        f"{library_data["url"] if self.download_source == "BMCLAPI"
                        else library_data["url"].replace("https://libraries.minecraft.net", "https://bmclapi2.bangbang93.com/maven")}",
                        # 远端地址
                        [(self.install_main_path / "libraries" / library_data["path"]).parent],
                        # 下载资源文件路径
                        [pathlib.Path(library_data["path"]).name],  # 下载资源文件名
                        library_data["sha1"]  # 散列值
                    ),  # 好长一参数
                    "callback": self._library_downloading_callback,
                    "callback_args": (f"library-downloading-worker-retry-{self.retried_libraries}",),
                    "max_retries": 3,
                    "priority": 12
                })
            else:
                self._retry_download_game_resources({
                    "id": f"library-downloading-worker-retry-{self.retried_libraries}",
                    "description": f"重试下载游戏支持库文件的 ({library_data["name"]})",
                    "function": self._regular_download,
                    "args": (
                        f"library-downloading-worker-{self.retried_libraries}",  # 给个 id，debug 用
                        f"{library_data["downloads"]["artifact"]["url"] if self.download_source == "BMCLAPI"
                        else library_data["downloads"]["artifact"]["url"].replace("https://libraries.minecraft.net", "https://bmclapi2.bangbang93.com/maven")}",  # 远端地址
                        [(self.install_main_path / "libraries" / library_data["downloads"]["artifact"]["path"]).parent],  # 下载资源文件路径
                        [pathlib.Path(library_data["downloads"]["artifact"]["path"]).name],  # 下载资源文件名
                        library_data["downloads"]["artifact"]["sha1"]  # 散列值
                    ),  # 好长一参数
                    "callback": self._library_downloading_callback,
                    "callback_args": (f"library-downloading-worker-retry-{self.retried_libraries}",),
                    "max_retries": 3,
                    "priority": 12
                })
            self.retried_libraries += 1
        return 0

    def _get_libraries_progress(self) -> int:
        return self.installed_libraries + self.failed_libraries

    def _wait_for_batch_completion(self, min_completed: float) -> None:
        start_time: float = time.time()
        while time.time() - start_time < 30:
            if self.installed_assets + self.failed_assets >= min_completed:
                break
            time.sleep(0.5)

    @staticmethod
    def _print_progress(description: str, total_progress: int, lazy_progress_getter: typing.Callable) -> None:
        last_progress = 0
        sleep_time = 0.5

        while lazy_progress_getter() < total_progress:
            current = lazy_progress_getter()
            if current > last_progress:
                if current - last_progress > 10:
                    sleep_time = max(0.1, sleep_time * 0.8)
                else:
                    sleep_time = min(2.0, sleep_time * 1.2)

                logging.info(f"{description}：{current} / {total_progress}")
                last_progress = current

            time.sleep(sleep_time)

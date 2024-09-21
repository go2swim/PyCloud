import json
import traceback
import hashlib
import os

import requests
import datetime

from src.Yandex.yandex_disk import format_datetime
from .OAuth_dropbox import DropboxHeadersManager
from src.cloud_interface import CloudInterface

URL = "https://api.dropboxapi.com/2/files"
DROPBOX_API_URL = "https://api.dropboxapi.com/2"
DROPBOX_CONTENT_URL = "https://content.dropboxapi.com/2"


class DropBox(CloudInterface):
    def __init__(self, dir_name, full_path):
        self.dir_name = dir_name
        self.full_path = full_path
        from src.clouds_manager import ROOT_FOLDER

        self.ROOT_FOLDER = ROOT_FOLDER
        self.headers = DropboxHeadersManager()

    def handle_response(self, response, retry_on_401=True):
        """Обработка ошибок HTTP-запросов с выводом стека вызовов при ошибках."""
        if 200 <= response.status_code < 300:
            return response.json() if response.content else {}
        else:
            try:
                error_info = response.json()
                error_message = error_info.get("error_summary", "Нет описания ошибки")
            except ValueError:
                error_message = response.text or "Нет описания ошибки"

            if response.status_code == 401 and retry_on_401:
                # Обновляем токен и повторяем запрос
                print("Ошибка 401: токен истёк. Обновление токена...")
                self.headers.token_manager.refresh_token()

                new_headers = self.headers.headers
                retry_response = requests.request(
                    method=response.request.method,
                    url=response.request.url,
                    headers=new_headers,
                    data=response.request.body,
                )

                return self.handle_response(retry_response, retry_on_401=False)

            error_text = f"Ошибка {response.status_code}: {error_message}"

            stack_trace = traceback.format_exc()

            raise Exception(f"{error_text}\nСтек вызовов:\n{stack_trace}")

    def create_folder(self, path):
        try:
            url = f"{DROPBOX_API_URL}/files/create_folder_v2"
            data = json.dumps({"path": path, "autorename": False})
            response = requests.post(url, headers=self.headers.headers, data=data)
            result = self.handle_response(response)
            if result:
                print(f"Папка '{path}' успешно создана.")
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при создании папки: {e}")

    def upload_file(self, loadfile, savefile, replace=False):
        try:
            url = f"{DROPBOX_CONTENT_URL}/files/upload"
            headers = self.headers.headers
            headers["Dropbox-API-Arg"] = json.dumps(
                {
                    "path": savefile,
                    "mode": "overwrite" if replace else "add",
                    "autorename": True,
                    "mute": False,
                }
            )
            headers["Content-Type"] = "application/octet-stream"

            with open(loadfile, "rb") as f:
                response = requests.post(url, headers=headers, data=f)
                result = self.handle_response(response)
                if result:
                    print(
                        f"Файл '{os.path.basename(loadfile)}' успешно загружен как '{savefile}'."
                    )
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при загрузке файла '{loadfile}': {e}")

    def delete(self, path):
        try:
            url = f"{DROPBOX_API_URL}/files/delete_v2"
            data = json.dumps({"path": path})
            response = requests.post(url, headers=self.headers.headers, data=data)
            result = self.handle_response(response)
            if result:
                print(f"Ресурс '{path}' успешно удален.")
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при удалении ресурса '{path}': {e}")

    def list_folder(self, path):
        url = f"{DROPBOX_API_URL}/files/list_folder"
        response = requests.post(
            url, headers=self.headers.headers, data=json.dumps({"path": path})
        )
        items = self.handle_response(response)
        return items

    def check_root_folder(self):
        items = self.list_folder("")
        return self.ROOT_FOLDER in [item["name"] for item in items.get("entries", [])]

    def check_upload(self):
        if not self.check_root_folder():
            self.create_folder(f"/{self.ROOT_FOLDER}")

        items = self.list_folder(f"/{self.ROOT_FOLDER}")
        if self.dir_name not in [item["name"] for item in items["entries"]]:
            self.create_folder(f"/{self.ROOT_FOLDER}/{self.dir_name}")
        # else:
        #     print(f'start dir {self.dir_name} is exist')

    def get_cloud_tree(self, folder_name, tree_list, root):
        root += folder_name + os.path.sep
        if folder_name == "":
            root = ""
        items = self.list_folder(
            f'/{self.ROOT_FOLDER}/{root.replace(os.path.sep, "/")}'
        )
        if not items:
            return

        for item in items["entries"]:
            if item[".tag"] != "folder":
                continue
            tree_list.append(root + item["name"])
            folder_name = item["name"]
            self.get_cloud_tree(folder_name, tree_list, root)

    def upload_dir_on_cloud(self, upload_folders):
        upload_folders = sorted(
            upload_folders, key=lambda input_str: input_str.count(os.path.sep)
        )

        for folder_dir in upload_folders:
            path = f"{os.path.sep.join(self.full_path.split(os.path.sep)[:-1])}{os.path.sep}{folder_dir}"
            files = [
                f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))
            ]

            self.create_folder(
                f'/{self.ROOT_FOLDER}/{folder_dir.replace(os.path.sep, "/")}'
            )

            for file_name in files:
                path_to_file_os = f"{folder_dir}\\{file_name}"
                self.upload_file(
                    path_to_file_os,
                    f'/{self.ROOT_FOLDER}/{path_to_file_os.replace(os.path.sep, "/")}',
                )

    def get_os_and_clouds_files(self, folder_dir, full_path):
        os_files = [
            f
            for f in os.listdir(full_path)
            if os.path.isfile(os.path.join(full_path, f))
        ]

        # Получаем файлы из Dropbox
        items = self.list_folder(
            f'/{self.ROOT_FOLDER}/{folder_dir.replace(os.path.sep, "/")}'
        )
        if not items:
            return os_files, []

        # Файлы в облаке
        cloud_files = [f for f in items["entries"] if f[".tag"] == "file"]

        return os_files, cloud_files

    def get_data_for_comparison(self, os_path_file, cloud_file):
        os_modified_time = datetime.datetime.fromtimestamp(
            os.path.getmtime(os_path_file)
        )
        os_modified_time = os_modified_time.replace(
            tzinfo=datetime.datetime.now().astimezone().tzinfo
        )

        cloud_modified_time = datetime.datetime.fromisoformat(
            cloud_file["server_modified"]
        )

        with open(os_path_file, "rb") as f:
            os_file_md5 = hashlib.md5(f.read()).hexdigest()

        cloud_file_md5 = cloud_file["content_hash"]

        return os_modified_time, cloud_modified_time, os_file_md5, cloud_file_md5

    def update_dir_on_cloud(self, exact_folders):
        for folder_dir in exact_folders:
            full_path = (
                os.path.sep.join(self.full_path.split(os.path.sep)[:-1])
                + os.path.sep
                + folder_dir
            )
            os_files, cloud_files = self.get_os_and_clouds_files(folder_dir, full_path)

            refresh_files = [f for f in cloud_files if f["name"] in os_files]
            remove_files = [f for f in cloud_files if f["name"] not in os_files]
            upload_files = [
                f for f in os_files if f not in [j["name"] for j in cloud_files]
            ]

            for cloud_file in refresh_files:
                os_path_file = os.path.join(full_path, cloud_file["name"])
                os_modified_time, cloud_modified_time, os_file_md5, cloud_file_md5 = (
                    self.get_data_for_comparison(os_path_file, cloud_file)
                )

                # по хэшу тут не сравнить, потомучто у них свои алгоритмы как его считать
                # if (os_modified_time > cloud_modified_time) or (cloud_file_md5 != os_file_md5):
                if os_modified_time > cloud_modified_time:
                    self.upload_file(
                        os_path_file, cloud_file["path_display"], replace=True
                    )

            for remove_file in remove_files:
                self.delete(remove_file["path_display"])

            for file_name in upload_files:
                self.upload_file(
                    os.path.join(full_path, file_name),
                    f'/{self.ROOT_FOLDER}/{folder_dir.replace(os.path.sep, "/")}/{file_name}',
                )

    def update_dir_on_pc(self, exact_folders):
        for folder_dir in exact_folders:
            from src.clouds_manager import get_os_path_by_cloud_path

            full_path = get_os_path_by_cloud_path(folder_dir)
            os_files, cloud_files = self.get_os_and_clouds_files(folder_dir, full_path)

            refresh_files = [f for f in cloud_files if f["name"] in os_files]
            remove_files = [
                f for f in os_files if f not in [j["name"] for j in cloud_files]
            ]
            download_files = [f for f in cloud_files if f["name"] not in os_files]

            for cloud_file in refresh_files:
                os_path_file = os.path.join(full_path, cloud_file["name"])
                os_modified_time, cloud_modified_time, os_file_md5, cloud_file_md5 = (
                    self.get_data_for_comparison(os_path_file, cloud_file)
                )

                if os_modified_time < cloud_modified_time:
                    self.download(
                        full_path, cloud_file["path_display"], is_folder=False
                    )
                    print(
                        f'Файл {cloud_file["name"]} обновлён в папке {os.path.basename(full_path)}'
                    )

            for remove_file in remove_files:
                os.remove(f"{full_path}{os.path.sep}{remove_file}")

            for clouds_download_file in download_files:
                self.download(
                    full_path, clouds_download_file["path_display"], is_folder=False
                )

    def remove_old_dir_on_cloud(self, remove_folders):
        for remove_folder in remove_folders:
            self.delete(
                f'/{self.ROOT_FOLDER}/{remove_folder.replace(os.path.sep, "/")}'
            )

    def list_files(self, path):
        result = []
        path = path.replace(os.path.sep, "/")
        if not path.startswith("/"):
            path = "/" + path

        url = f"{DROPBOX_API_URL}/files/list_folder"
        data = json.dumps({"path": path, "limit": 1000})
        response = requests.post(url, headers=self.headers.headers, data=data)
        folder_info = self.handle_response(response)

        if not folder_info:
            print("Путь не корректен")
            return []

        items = folder_info.get("entries", [])
        from ..clouds_manager import FileData

        for item in items:
            result.append(
                FileData(
                    item_type="DIR" if item[".tag"] == "folder" else "FILE",
                    item_name=item["name"],
                    item_size=item.get("size", None),
                    item_modified=(
                        datetime.datetime.fromisoformat(item.get("server_modified"))
                        if item.get("server_modified")
                        else None
                    ),
                )
            )

        return result

    def downloading_folders(self, download_folders):
        download_folders = sorted(
            download_folders, key=lambda input_str: input_str.count(os.path.sep)
        )

        for clouds_folder in download_folders:
            from src.clouds_manager import get_os_path_by_cloud_path

            root_path = get_os_path_by_cloud_path(
                clouds_folder
            )  # D:\...\SyncFolder\clouds_folder

            if os.path.exists(root_path):
                continue

            self.download(
                os.path.sep.join(root_path.split(os.path.sep)[:-1]),
                f"/{self.ROOT_FOLDER}/{clouds_folder.replace('\\', '/')}",
                is_folder=True,
            )

    def download(self, downloaded_path, save_path, is_folder=False):
        """Основной метод для загрузки файлов и папок из Dropbox."""
        if is_folder:
            items = self.list_folder(save_path)

            local_folder_path = os.path.join(
                downloaded_path, os.path.basename(save_path)
            )
            os.makedirs(local_folder_path, exist_ok=True)

            for item in items["entries"]:
                if item[".tag"] == "file":
                    self.download_file(local_folder_path, item["path_display"])
        else:
            self.download_file(downloaded_path, save_path)

    def download_file(self, downloaded_path, save_path):
        url = f"{DROPBOX_CONTENT_URL}/files/download"
        headers = {
            "Authorization": f"Bearer {self.headers.token}",
            "Dropbox-API-Arg": json.dumps({"path": f"{save_path}"}),
        }

        response = requests.post(url, headers=headers, stream=True)
        if response.status_code == 200:
            file_name = os.path.basename(save_path)
            file_path = os.path.join(downloaded_path, file_name)

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"Файл '{file_name}' успешно скачан.")
        else:
            self.handle_response(response)

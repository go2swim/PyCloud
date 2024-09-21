from __future__ import print_function

import hashlib
import mimetypes
import io

import apiclient
import httplib2
import datetime
import os
import pickle

from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from oauth2client import client
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

from src.cloud_interface import CloudInterface
from src.Yandex.yandex_disk import format_datetime

TIME_DELTA = datetime.timedelta(seconds=5)
SCOPES = ["https://www.googleapis.com/auth/drive"]
APPLICATION_NAME = "Drive API Python Quickstart"
GOOGLE_MIME_TYPES = {  # нужны для определения файлов google_docs и последующей конвертации для загрузки {docs: os_type}
    "application/vnd.google-apps.document": [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ],
    # 'application/vnd.google-apps.document':
    # 'application/vnd.oasis.opendocument.text',
    "application/vnd.google-apps.spreadsheet": [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ],
    # 'application/vnd.oasis.opendocument.spreadsheet',
    "application/vnd.google-apps.presentation": [
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ],
}


def get_service():
    creds = None
    current_dir = os.path.basename(os.getcwd())
    if current_dir == "PyCloud":
        token_path = os.path.join("src", "Drive", "token.pickle")
    elif current_dir == "src":
        token_path = os.path.join("Drive", "token.pickle")
    elif current_dir == "Yandex":
        token_path = "token.pickle"
    else:
        raise FileNotFoundError("Is start directory not found")

    # Загружаем токен, если он уже существует
    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)

    # Если токен недействителен или отсутствует, выполняем аутентификацию
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # client_secrets_file = 'credentials.json'
            current_dir = os.path.basename(os.getcwd())
            if current_dir == "PyCloud":
                client_secrets_file = os.path.join("src", "Drive", "credentials.json")
            elif current_dir == "src":
                client_secrets_file = os.path.join("Drive", "credentials.json")
            elif current_dir == "Yandex":
                client_secrets_file = "credentials.json"
            else:
                raise FileNotFoundError("Is start directory not found")

            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, SCOPES
            )

            creds = flow.run_local_server(port=0)

        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

    service = build("drive", "v3", credentials=creds)
    return service


def handle_response(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except client.AccessTokenRefreshError:
            print(
                "The credentials have been revoked or expired, please re-authenticate."
            )
        except httplib2.ServerNotFoundError:
            print("No internet connection available.")
        except apiclient.errors.HttpError as error:
            code = error.resp.status
            if code == 403:
                print("Access denied: the user does not have sufficient permissions.")
            elif code == 404:
                print("File or folder not found.")
            elif code == 500:
                print("Internal server error, try again later.")
            elif code == 503:
                print("Service unavailable, try again later.")
            else:
                print(f"An HTTP error occurred: {error}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            raise e

    return wrapper


class GoogleDrive(CloudInterface):
    def __init__(self, dir_name, full_path):
        self.service = get_service()
        self.dir_name = dir_name
        self.full_path = full_path
        from src.clouds_manager import ROOT_FOLDER

        self.ROOT_FOLDER = ROOT_FOLDER
        if dir_name != "":
            self.folder_id = self.check_upload()

    @handle_response
    def check_upload(self):
        results = (
            self.service.files()
            .list(
                pageSize=100,
                q="'root' in parents and trashed != True and \
            mimeType='application/vnd.google-apps.folder'",
            )
            .execute()
        )

        items = results.get("files", [])

        if self.ROOT_FOLDER in [item["name"] for item in items]:
            root_folder_id = list(
                filter(lambda item: item["name"] == self.ROOT_FOLDER, items)
            )[0]["id"]
        else:
            folder_metadata = {
                "name": self.ROOT_FOLDER,
                # 'parents': [pre_last_dir],
                "mimeType": "application/vnd.google-apps.folder",
            }
            create_folder = (
                self.service.files().create(body=folder_metadata, fields="id").execute()
            )
            root_folder_id = create_folder.get("id", [])
            print(f"Корневая папка {self.ROOT_FOLDER} создана")

        q = f"'{root_folder_id}' in parents and trashed = false and mimeType = 'application/vnd.google-apps.folder'"
        results = self.service.files().list(pageSize=100, q=q).execute()
        items = results.get("files")

        if self.dir_name in [item["name"] for item in items]:
            folder_id = [item["id"] for item in items if item["name"] == self.dir_name][
                0
            ]
        else:
            parents_id = self.root_folder_upload(root_folder_id)
            folder_id = parents_id[self.dir_name]
            print(f"Отслеживаемая папка {self.dir_name} загружена на облако")

        return folder_id

    @handle_response
    def root_folder_upload(self, root_folder_id):
        parents_id = {}
        for root, _, files in os.walk(self.full_path, topdown=True):
            last_dir = root.split("\\")[-1]
            pre_last_dir = root.split("\\")[-2]
            if pre_last_dir not in parents_id.keys():
                pre_last_dir = root_folder_id
            else:
                pre_last_dir = parents_id[pre_last_dir]

            folder_metadata = {
                "name": last_dir,
                "parents": [pre_last_dir],
                "mimeType": "application/vnd.google-apps.folder",
            }
            create_folder = (
                self.service.files().create(body=folder_metadata, fields="id").execute()
            )
            folder_id = create_folder.get("id", [])

            for name in files:
                file_metadata = {"name": name, "parents": [folder_id]}
                media = MediaFileUpload(
                    os.path.join(root, name),
                    mimetype=mimetypes.MimeTypes().guess_type(name)[0],
                )
                self.service.files().create(
                    body=file_metadata, media_body=media, fields="id"
                ).execute()

            parents_id[last_dir] = folder_id

        return parents_id

    @handle_response
    def get_cloud_tree(self, folder_name, tree_list, root):
        if folder_name == "":
            folder_name = self.ROOT_FOLDER
            self.parents_id = {self.ROOT_FOLDER: self.root_id}
        else:
            folder_name = self.full_path.split(os.path.sep)[-1]
            self.parents_id = {folder_name: self.folder_id}

        self.get_drive_tree(folder_name, tree_list, root)

    @handle_response
    def get_drive_tree(self, folder_name, tree_list, root):
        folder_id = self.parents_id[folder_name]

        # получаем список папок
        results = (
            self.service.files()
            .list(
                pageSize=100,
                q=(
                    "%r in parents and \
            mimeType = 'application/vnd.google-apps.folder'and \
            trashed != True"
                    % folder_id
                ),
            )
            .execute()
        )

        items = results.get("files", [])
        root += folder_name + os.path.sep

        for item in items:
            self.parents_id[item["name"]] = item["id"]
            tree_list.append(root + item["name"])
            folder_name = item["name"]
            self.get_drive_tree(folder_name, tree_list, root)

    @handle_response
    def upload_dir_on_cloud(self, upload_folders):
        upload_folders = sorted(
            upload_folders, key=lambda input_str: input_str.count(os.path.sep)
        )
        for folder_dir in upload_folders:
            var = os.path.split(self.full_path)[0] + os.path.sep
            variable = var + folder_dir
            last_dir = folder_dir.split(os.path.sep)[-1]
            pre_last_dir = folder_dir.split(os.path.sep)[-2]

            files = [
                f
                for f in os.listdir(variable)
                if os.path.isfile(os.path.join(variable, f))
            ]

            folder_metadata = {
                "name": last_dir,
                "parents": [self.parents_id[pre_last_dir]],
                "mimeType": "application/vnd.google-apps.folder",
            }
            create_folder = (
                self.service.files().create(body=folder_metadata, fields="id").execute()
            )
            print(f"Папка {last_dir} успешно создана")
            folder_id = create_folder.get("id", [])
            self.parents_id[last_dir] = folder_id

            for os_file in files:
                some_metadata = {"name": os_file, "parents": [folder_id]}
                os_file_mimetype = mimetypes.MimeTypes().guess_type(
                    os.path.join(variable, os_file)
                )[0]
                media = MediaFileUpload(
                    os.path.join(variable, os_file), mimetype=os_file_mimetype
                )
                upload_this = (
                    self.service.files()
                    .create(body=some_metadata, media_body=media, fields="id")
                    .execute()
                )
                upload_this = upload_this.get("id", [])
                print(f"Файл {os_file} загружен в {last_dir}")

    @handle_response
    def get_os_and_cloud_files(self, folder_id, os_path):
        os_files = [
            f for f in os.listdir(os_path) if os.path.isfile(os.path.join(os_path, f))
        ]

        results = (
            self.service.files()
            .list(
                pageSize=1000,
                q=(
                    f'"{folder_id}" in parents and \
                                mimeType!="application/vnd.google-apps.folder" and \
                                trashed != True'
                ),
                fields="files(id, name, mimeType, modifiedTime, md5Checksum)",
            )
            .execute()
        )
        clouds_files = results.get("files", [])

        return os_files, clouds_files

    @handle_response
    def get_data_for_comparison(self, path_to_file, drive_file, clouds_files):
        file_dir = os.path.join(path_to_file, drive_file["name"])
        os_modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_dir))
        os_modified_time = os_modified_time.replace(
            tzinfo=datetime.datetime.now().astimezone().tzinfo
        )
        mtime = [
            f["modifiedTime"] for f in clouds_files if f["name"] == drive_file["name"]
        ][0]
        cloud_modified_time = datetime.datetime.fromisoformat(mtime)
        os_file_md5 = hashlib.md5(open(file_dir, "rb").read()).hexdigest()
        if "md5Checksum" in drive_file.keys():
            drive_md5 = drive_file["md5Checksum"]
        else:
            drive_md5 = None

        return os_modified_time, cloud_modified_time, os_file_md5, drive_md5

    @handle_response
    def update_dir_on_cloud(self, exact_folders):
        for folder_dir in exact_folders:
            from src.clouds_manager import get_os_path_by_cloud_path

            os_path = get_os_path_by_cloud_path(folder_dir)
            os_files, clouds_files = self.get_os_and_cloud_files(
                self.parents_id[os.path.basename(folder_dir)], os_path
            )
            last_dir = os.path.split(folder_dir)[1]

            refresh_files = [f for f in clouds_files if f["name"] in os_files]
            remove_files = [f for f in clouds_files if f["name"] not in os_files]
            upload_files = [
                f for f in os_files if f not in [j["name"] for j in clouds_files]
            ]

            for drive_file in refresh_files:
                # используем время последнего апдейта и кеш, т.к у объектов могут быть одинаковое название а содержание
                # разное, и орентироваться только по времени в этом случае не получится

                os_modified_time, cloud_modified_time, os_file_md5, drive_md5 = (
                    self.get_data_for_comparison(os_path, drive_file, clouds_files)
                )

                a = abs(os_modified_time - cloud_modified_time)
                if os_modified_time - cloud_modified_time > TIME_DELTA or (
                    drive_file["mimeType"] != "application/vnd.google-apps.document"
                    and drive_md5 != os_file_md5
                ):
                    file_id = [
                        f["id"] for f in clouds_files if f["name"] == drive_file["name"]
                    ][0]
                    file_mime = [
                        f["mimeType"]
                        for f in clouds_files
                        if f["name"] == drive_file["name"]
                    ][0]

                    file_metadata = {
                        "name": drive_file["name"],
                        "parents": [self.parents_id[last_dir]],
                    }
                    media_body = MediaFileUpload(
                        os.path.join(os_path, drive_file["name"]), mimetype=file_mime
                    )
                    self.service.files().update(
                        fileId=file_id, media_body=media_body, fields="id"
                    ).execute()
                    print(f'Файл {drive_file["name"]} успешно обновлён')

            for drive_file in remove_files:
                file_id = [
                    f["id"] for f in clouds_files if f["name"] == drive_file["name"]
                ][0]
                self.service.files().delete(fileId=file_id).execute()
                print(f'Файл {drive_file["name"]} успешно удалён на облаке')

            for os_file in upload_files:
                file_dir = os.path.join(os_path, os_file)

                # File's new content.
                filemime = mimetypes.MimeTypes().guess_type(file_dir)[0]
                file_metadata = {
                    "name": os_file,
                    "parents": [self.parents_id[last_dir]],
                }
                media_body = MediaFileUpload(file_dir, mimetype=filemime)

                self.service.files().create(
                    body=file_metadata, media_body=media_body, fields="id"
                ).execute()
                print(f"Файл {os_file} успешно загружен в {last_dir}")

    @handle_response
    def remove_old_dir_on_cloud(self, remove_folders):
        remove_folders = sorted(
            remove_folders,
            key=lambda input_str: input_str.count(os.path.sep),
            reverse=True,
        )

        for folder_dir in remove_folders:
            var = (os.path.sep).join(
                self.full_path.split(os.path.sep)[0:-1]
            ) + os.path.sep
            variable = var + folder_dir
            last_dir = folder_dir.split(os.path.sep)[
                -1
            ]  # получаем название фала чтобы получит id
            folder_id = self.parents_id[last_dir]
            self.service.files().delete(fileId=folder_id).execute()  # и удаляем по id
            print(f"Папка {last_dir} успешно удалена с облака")

    @handle_response
    def check_root_folder(self):
        results = (
            self.service.files()
            .list(
                pageSize=100,
                q="'root' in parents and trashed != True and mimeType='application/vnd.google-apps.folder'",
            )
            .execute()
        )
        items = results.get("files", [])
        root_folder = list(filter(lambda x: x["name"] == self.ROOT_FOLDER, items))
        if root_folder:
            self.root_id = root_folder[0]["id"]

        return root_folder

    @handle_response
    def downloading_folders(self, download_folders):
        download_folders = sorted(
            download_folders, key=lambda input_str: input_str.count(os.path.sep)
        )
        for folder_dir in download_folders:
            from src.clouds_manager import get_os_path_by_cloud_path

            os_path = get_os_path_by_cloud_path(folder_dir)
            last_dir = folder_dir.split(os.path.sep)[-1]

            folder_id = self.parents_id[last_dir]
            results = (
                self.service.files()
                .list(pageSize=20, q=("%r in parents" % folder_id))
                .execute()
            )

            items = results.get("files", [])
            os.makedirs(os_path)
            print(f"Папка {os.path.basename(os_path)} создана на пк")
            files = [
                f
                for f in items
                if f["mimeType"] != "application/vnd.google-apps.folder"
            ]

            for drive_file in files:
                self.download_file_from_drive(os_path, drive_file)
                print(
                    f'Файл {drive_file["name"]} загружен в папку {os.path.basename(os_path)}'
                )

    @handle_response
    def download_file_from_drive(self, file_path, drive_file):
        file_id = drive_file["id"]
        file_name = drive_file["name"]
        if drive_file["mimeType"] in GOOGLE_MIME_TYPES.keys():
            if file_name.endswith(GOOGLE_MIME_TYPES[drive_file["mimeType"]][1]):
                file_name = drive_file["name"]
            else:
                file_name = "{}{}".format(
                    drive_file["name"], GOOGLE_MIME_TYPES[drive_file["mimeType"]][1]
                )
                self.service.files().update(
                    fileId=file_id, body={"name": file_name}
                ).execute()

            request = (
                self.service.files()
                .export(
                    fileId=file_id,
                    mimeType=(GOOGLE_MIME_TYPES[drive_file["mimeType"]])[0],
                )
                .execute()
            )
            with io.FileIO(os.path.join(file_path, file_name), "wb") as file_write:
                file_write.write(request)

        else:
            request = self.service.files().get_media(fileId=file_id)
            file_io = io.FileIO(os.path.join(file_path, drive_file["name"]), "wb")
            downloader = MediaIoBaseDownload(file_io, request)
            done = False
            while done is False:
                _, done = downloader.next_chunk()

    def update_dir_on_pc(self, exact_folders):
        for folder_dir in exact_folders:
            from src.clouds_manager import get_os_path_by_cloud_path

            os_path = get_os_path_by_cloud_path(folder_dir)
            os_files, cloud_files = self.get_os_and_cloud_files(
                self.parents_id[os.path.split(folder_dir)[1]], os_path
            )
            last_dir = os.path.split(folder_dir)[1]

            refresh_files = [f for f in cloud_files if f["name"] in os_files]
            remove_files = [
                f for f in os_files if f not in [j["name"] for j in cloud_files]
            ]
            download_files = [f for f in cloud_files if f["name"] not in os_files]

            for drive_file in refresh_files:
                os_modified_time, cloud_modified_time, os_file_md5, drive_md5 = (
                    self.get_data_for_comparison(os_path, drive_file, refresh_files)
                )

                if (
                    cloud_modified_time - os_modified_time > TIME_DELTA
                    or drive_file["mimeType"] != "application/vnd.google-apps.document"
                    and drive_md5 != os_file_md5
                ):
                    os.remove(os.path.join(os_path, drive_file["name"]))
                    self.download_file_from_drive(os_path, drive_file)
                    print(f'Файл {drive_file["name"]} обновлён на пк')

            for os_file in remove_files:
                os.remove(os.path.join(os_path, os_file))
                print(f"Файл {os.path.basename(os_file)} удалён с пк")

            for drive_file in download_files:
                self.download_file_from_drive(os_path, drive_file)
                print(f'Файл {drive_file["name"]} загружен на пк')

    @handle_response
    def list_files(self, path):
        result = []

        # чтобы забить словарик id
        self.get_cloud_tree("", [], "")

        try:
            query = f"'{self.parents_id[os.path.basename(path)]}' in parents and trashed = false"
            response = (
                self.service.files()
                .list(
                    q=query,
                    fields="files(id, name, mimeType, size, modifiedTime)",
                    pageSize=1000,
                )
                .execute()
            )

            items = response.get("files", [])

            from src.clouds_manager import FileData

            for item in items:
                item_type = (
                    "DIR"
                    if item["mimeType"] == "application/vnd.google-apps.folder"
                    else "FILE"
                )

                item_size = item.get("size", None)
                item_modified = (
                    format_datetime(item["modifiedTime"])
                    if "modifiedTime" in item
                    else None
                )

                result.append(
                    FileData(
                        item_type=item_type,
                        item_name=item["name"],
                        item_size=item_size,
                        item_modified=item_modified,
                    )
                )

            return result

        except Exception as e:
            print(f"Ошибка при получении информации о папке: {e}")
            return result

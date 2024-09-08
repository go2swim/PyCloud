import hashlib
import mimetypes
import os
import datetime
import urllib

import requests
import zipfile
from cloud_interface import CloudInterface

URL = 'https://cloud-api.yandex.net/v1/disk/resources'
TOKEN = 'y0_AgAAAAA-fOi6AAxLZQAAAAEOOar3AADAEGooJ61N-byf4jKn_Duv4Y7AzQ'
headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Authorization': f'OAuth {TOKEN}'}


class YandexDisk(CloudInterface):
    def __init__(self, dir_name, full_path):
        self.dir_name = dir_name
        self.full_path = full_path
        import work_with_cloud
        self.ROOT_FOLDER = work_with_cloud.ROOT_FOLDER

    def handle_response(self, response):
        """Обработка ошибок HTTP-запросов"""
        if response.status_code in range(200, 300):
            return response.json() if response.content else {}
        else:
            error_info = response.json()
            print(f"Ошибка {response.status_code}: {error_info.get('message', 'Нет описания ошибки')}")

    def create_folder(self, path):
        """Создание папки. \n path: Путь к создаваемой папке."""
        try:
            response = requests.put(f'{URL}?path={path}', headers=headers)
            self.handle_response(response)
            print(f"Папка '{path}' успешно создана.")
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при создании папки: {e}")

    def upload_file(self, loadfile, savefile, replace=False):
        """Загрузка файла.
        savefile: Путь к загружаемому файлу
        loadfile: Путь к файлу на Диске
        replace: true or false Замена файла на Диске"""
        try:
            # Получаем ссылку на загрузку
            response = requests.get(f'{URL}/upload?path={savefile}&overwrite={replace}', headers=headers)
            res = self.handle_response(response)
            href = res.get('href')
            if href:
                with open(loadfile, 'rb') as f:
                    upload_response = requests.put(href, files={'file': f})
                    self.handle_response(upload_response)
                    print(f"Файл '{os.path.basename(loadfile)}' успешно загружен как '{savefile}'.")
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при загрузке файла '{loadfile}': {e}")

    def delete(self, path):
        """Удаление папки/файла"""
        try:
            response = requests.delete(f'{URL}?path={path}', headers=headers)
            self.handle_response(response)
            print(f"Ресурс '{path}' успешно удален.")
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при удалении ресурса '{path}': {e}")

    def download(self, downloaded_path, save_path, is_folder):
        response = requests.get(f'{URL}/download?path={self.ROOT_FOLDER}/{downloaded_path}', headers=headers)
        res = self.handle_response(response)
        href = res.get('href')

        if not href:
            print(f"Не удалось получить ссылку на скачивание {downloaded_path}")

        if is_folder:
            try:
                # Получаем ссылку на скачивание
                response = requests.get(f'{URL}/download?path={self.ROOT_FOLDER}/{downloaded_path}', headers=headers)
                res = self.handle_response(response)
                href = res.get('href')

                if href:
                    download_response = requests.get(href)
                    archive_path = os.path.join(save_path, 'archive.zip')

                    # Сохраняем файл на диск
                    with open(archive_path, 'wb') as file:
                        file.write(download_response.content)
                    # print(f"Файл '{archive_path}' успешно скачан.")

                    # Распаковываем ZIP-архив
                    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                        zip_ref.extractall(save_path)
                    # print(f"Архив распакован в '{save_path}'.")

                    # Удаляем скачанный ZIP-файл после распаковки
                    os.remove(archive_path)
                    # print(f"Архив '{archive_path}' удален после распаковки.")
                    print(f'Папка {os.path.split(downloaded_path)[1]} успешно скачана')
                else:
                    print("Не удалось получить ссылку на скачивание.")
            except requests.exceptions.RequestException as e:
                print(f"Ошибка при скачивании файла: {e}")
            except zipfile.BadZipFile:
                print(f"Файл по пути '{archive_path}' не является корректным ZIP-архивом.")

        else:  # Если это файл, то скачиваем его
            file_name = urllib.parse.unquote(href.split("filename=")[1].split("&")[0])
            file_save_path = os.path.join(save_path, file_name)

            with open(file_save_path, "wb") as file:
                download_response = requests.get(href, stream=True)
                for chunk in download_response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(chunk)
                        file.flush()

            print(f"Файл {file_name} успешно скачан в {file_save_path}")

    def downloading_folders(self, download_folders):
        download_folders = sorted(download_folders, key=lambda input_str: input_str.count(os.path.sep))
        for clouds_folder in download_folders:
            from work_with_cloud import get_os_path_by_cloud_path
            root_path = get_os_path_by_cloud_path(clouds_folder)  # D:\...\SyncFolder\clouds_folder[1:]
            if os.path.exists(root_path):
                continue
            self.download(clouds_folder.replace('\\', '/'),
                          os.path.sep.join(root_path.split(os.path.sep)[:-1]), is_folder=True)

    def list_files(self, path):
        """Выводит информацию о файлах и папках по заданному пути."""
        result = []
        path = path.replace(os.path.sep, '/')

        try:
            response = requests.get(f'{URL}?path={path}&limit=1000', headers=headers)
            folder_info = self.handle_response(response)
            if not folder_info:
                print('Путь не корректен')
                return []

            items = folder_info.get('_embedded', {}).get('items', [])

            from work_with_cloud import FileData
            for item in items:
                result.append(FileData(
                    item_type="DIR" if item['type'] == "dir" else "FILE",
                    item_name=item['name'],
                    item_size=item['size'] if 'size' in item else None,
                    item_modified=format_datetime(item['modified'])
                ))

            return result

        except requests.exceptions.RequestException as e:
            print(f"Ошибка при получении информации о папке: {e}")

    def check_root_folder(self):
        response = requests.get(f'{URL}?path=/', headers=headers)
        items = self.handle_response(response)
        return self.ROOT_FOLDER in [item['name'] for item in items['_embedded']['items']]

    def check_upload(self):
        if not self.check_root_folder():
            self.create_folder(f'{self.ROOT_FOLDER}')

        response = requests.get(f'{URL}?path=/{self.ROOT_FOLDER}', headers=headers)
        items = self.handle_response(response)
        if self.dir_name not in [item['name'] for item in items['_embedded']['items']]:
            self.create_folder(f'{self.ROOT_FOLDER}/{self.dir_name}')
        # else:
        #     print(f'start dir {self.dir_name} is exist')

    def get_cloud_tree(self, folder_name, tree_list, root):
        root += folder_name + os.path.sep
        if folder_name == '':
            root = ''
        # получаем список папок
        request = requests.get(f'{URL}?path=/{self.ROOT_FOLDER}/{root.replace(os.path.sep, '/')}', headers=headers)
        response = self.handle_response(request)

        items = response['_embedded']['items']

        for item in items:
            if item['type'] != 'dir':
                continue
            tree_list.append(root + item['name'])
            folder_name = item['name']
            self.get_cloud_tree(folder_name, tree_list, root)

    def upload_dir_to_cloud(self, upload_folders):
        upload_folders = sorted(upload_folders, key=lambda input_str: input_str.count(os.path.sep))

        for folder_dir in upload_folders:
            path = f'{'\\'.join(self.full_path.split(os.path.sep)[:-1])}{os.path.sep}{folder_dir}'

            files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]

            self.create_folder(f'{self.ROOT_FOLDER}/{folder_dir.replace(os.path.sep, '/')}')

            for file_name in files:
                path_to_file_os = f'{folder_dir}\\{file_name}'
                self.upload_file(path_to_file_os,
                                 self.ROOT_FOLDER + '/' + path_to_file_os.replace(os.path.sep, '/'))

    def get_os_and_clouds_files(self, folder_dir, full_path):
        os_files = [f for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f))]

        request = requests.get(
            f'{URL}?path=/{self.ROOT_FOLDER}/{folder_dir.replace(os.path.sep, '/')}', headers=headers)
        response = self.handle_response(request)

        cloud_files = [f for f in response['_embedded']['items'] if f['type'] == 'file']

        return os_files, cloud_files

    def get_data_for_comparison(self, os_path_file, cloud_file):
        os_modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(os_path_file))
        os_modified_time = os_modified_time.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)
        cloud_modified_time = datetime.datetime.fromisoformat(cloud_file['modified'])

        os_file_md5 = hashlib.md5(open(os_path_file, 'rb').read()).hexdigest()
        cloud_file_md5 = cloud_file['md5']

        return os_modified_time, cloud_modified_time, os_file_md5, cloud_file_md5

    def update_dir_on_cloud(self, exact_folders):
        for folder_dir in exact_folders:
            full_path = '\\'.join(self.full_path.split(os.path.sep)[:-1]) + '\\' + folder_dir
            os_files, cloud_files = self.get_os_and_clouds_files(folder_dir, full_path)

            refresh_files = [f for f in cloud_files if f['name'] in os_files]
            remove_files = [f for f in cloud_files if f['name'] not in os_files]
            upload_files = [f for f in os_files if f not in [j['name'] for j in cloud_files]]

            for cloud_file in refresh_files:
                os_path_file = os.path.join(full_path, cloud_file['name'])
                os_modified_time, cloud_modified_time, os_file_md5, cloud_file_md5 = (
                    self.get_data_for_comparison(os_path_file, cloud_file))

                if (os_modified_time > cloud_modified_time) or (cloud_file_md5 != os_file_md5):
                    #  на диске нет обновления файла, можно только загрузить и заменить:(
                    self.upload_file(os_path_file, cloud_file['path'], replace=True)

            for remove_file in remove_files:
                self.delete(remove_file['path'])

            for file_name in upload_files:
                self.upload_file(os.path.join(full_path, file_name),
                                 f'{self.ROOT_FOLDER}/{folder_dir.replace(os.path.sep, '/')}/{file_name}')

    def update_dir_on_pc(self, exact_folders):
        for folder_dir in exact_folders:
            from work_with_cloud import get_os_path_by_cloud_path
            full_path = get_os_path_by_cloud_path(folder_dir)
            os_files, cloud_files = self.get_os_and_clouds_files(folder_dir, full_path)

            refresh_files = [f for f in cloud_files if f['name'] in os_files]
            remove_files = [f for f in os_files if f not in [j['name'] for j in cloud_files]]
            download_files = [f for f in cloud_files if f['name'] not in os_files]

            for cloud_file in refresh_files:
                os_path_file = os.path.join(full_path, cloud_file['name'])
                os_modified_time, cloud_modified_time, os_file_md5, cloud_file_md5 = (
                    self.get_data_for_comparison(os_path_file, cloud_file))

                if (os_modified_time < cloud_modified_time) or (cloud_file_md5 != os_file_md5):
                    self.download(cloud_file['path'].split(self.ROOT_FOLDER)[-1][1:], full_path, is_folder=False)

            for remove_file in remove_files:
                os.remove(f'{full_path}{os.path.sep}{remove_file}')

            for clouds_download_file in download_files:
                os_path = get_os_path_by_cloud_path(clouds_download_file['path'].replace('/', os.path.sep))
                self.download('/'.join(clouds_download_file['path'].split('/')[2:]),
                              os.path.sep.join(os_path.split(os.path.sep)[:-1]), is_folder=False)

    def remove_old_dir_on_cloud(self, remove_folders):
        for remove_folder in remove_folders:
            self.delete(f'{self.ROOT_FOLDER}/{remove_folder.replace(os.path.sep, '/')}')


def format_datetime(iso_date):
    return datetime.datetime.fromisoformat(iso_date.replace("Z", "+00:00"))


if __name__ == '__main__':
    pass

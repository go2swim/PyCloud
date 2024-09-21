import os.path
import datetime
import shutil
import re
from dataclasses import dataclass

from src.Yandex.yandex_disk import YandexDisk
from src.Drive.google_drive import GoogleDrive
from src.Dropbox.dropbox import DropBox


CLOUDS = {'yandex': lambda folder_full_path: YandexDisk(os.path.basename(folder_full_path), folder_full_path),
          'google': lambda folder_full_path: GoogleDrive(os.path.basename(folder_full_path), folder_full_path),
          'dropbox': lambda folder_full_path: DropBox(os.path.basename(folder_full_path), folder_full_path)}
SAVE_SYNC_FILE = r'save_sync_folder.txt' if os.path.basename(os.getcwd()) == 'src' \
    else os.path.join('src', 'save_sync_folder.txt')
ROOT_FOLDER = 'SYNC_FOLDERS'

def remove_sync_folder(folder_path):
    try:
        with open(SAVE_SYNC_FILE, 'r') as file:
            paths = [line.strip() for line in file.readlines()]

        paths.remove(folder_path)

        with open(SAVE_SYNC_FILE, 'w') as file:
            for path in paths:
                file.write(path + '\n')
    except FileNotFoundError:
        print('Нет отслеживаемых папок')

def get_and_update_sync_folders():
    """returns a list of existing paths and deleting all non-existing paths from the file"""
    try:
        with open(SAVE_SYNC_FILE, 'r') as file:
            paths = [line.strip() for line in file.readlines()]

        existing_paths = [path for path in paths if os.path.exists(path)]

        # Если список существующих путей меньше исходного списка, нужно перезаписать файл
        if len(existing_paths) < len(paths):
            print(f'Путь: {set(paths).difference(set(existing_paths))} больше не актуален, '
                  f'поэтому удалён из отслеживаемых')
            with open(SAVE_SYNC_FILE, 'w') as file:
                for path in existing_paths:
                    file.write(path + '\n')

        return existing_paths

    except FileNotFoundError:
        print('Нет отслеживаемых папок')
        return []


def save_sync_folders(path):
    try:
        with open(SAVE_SYNC_FILE, 'r') as file:
            if path in [line.split('\n')[0] for line in file.readlines()]:
                print('Path is exist')
                return
    except FileNotFoundError:
        pass

    with open(SAVE_SYNC_FILE, 'a') as file:
        file.write(f'{path}\n')


def get_os_tree(full_path):
    root_len = len(full_path.split(os.path.sep)[0:-2])
    os_tree_list = []
    for root, dirs, files in os.walk(full_path, topdown=True):
        for name in dirs:
            var_path = os.path.sep.join(root.split(os.path.sep)[root_len + 1:])
            os_tree_list.append(os.path.join(var_path, name))

    return os_tree_list

def sync_folders(list_clouds=[]):
    sync_folders = get_and_update_sync_folders()

    if list_clouds:
        get_clouds = [v for k, v in CLOUDS.items() if k in list_clouds]
    else:
        get_clouds = CLOUDS.values()

    for get_cloud in get_clouds:
        print(f'Синхронизация {get_cloud("").__class__.__name__}')
        for folder_full_path in sync_folders:
            cloud = get_cloud(folder_full_path)
            name_folder = os.path.basename(folder_full_path)

            cloud.check_upload()

            tree_list = []
            cloud.get_cloud_tree(name_folder, tree_list, '')
            # print(tree_list)
            os_tree_list = get_os_tree(folder_full_path)

            # папки которые есть в drive но нет на пк - удаляем
            remove_folders = list(set(tree_list).difference(set(os_tree_list)))
            # папки, которые есть на пк, но нет на облаке - загружаем
            upload_folders = list(set(os_tree_list).difference(set(tree_list)))
            # папки, которые есть и там и там, обновляем в них файлы
            exact_folders = list(set(os_tree_list).intersection(set(tree_list)))  # SYNC_FOLDER\1\2...
            exact_folders.append(name_folder)  # добавим в обновляемые исходную папку

            cloud.upload_dir_on_cloud(upload_folders)

            cloud.update_dir_on_cloud(exact_folders)

            cloud.remove_old_dir_on_cloud(remove_folders)

def sync_locals_folders(cloud_name):
    if cloud_name:
        get_cloud = CLOUDS[cloud_name]
    else:
        get_cloud = CLOUDS['yandex']

    cloud = get_cloud('')

    if not cloud.check_root_folder():
        print('На облаке нет ранее синхронизированных папок')
        return

    tree_list = []
    cloud.get_cloud_tree('', tree_list, '')
    tree_list = [re.split(fr'{ROOT_FOLDER}\\', path)[-1] for path in tree_list]
    # print(tree_list)

    os_tree_list = []
    sync_folders = get_and_update_sync_folders()
    for monitored_folder in sync_folders:
        os_tree_list += get_os_tree(monitored_folder)
    os_tree_list += [os.path.basename(f) for f in sync_folders]
    # print(os_tree_list)

    # папки которые есть в drive но нет на пк
    download_folders = list(set(tree_list).difference(set(os_tree_list)))
    # папки, которые есть на пк, но нет на облаке
    remove_folders = list(set(os_tree_list).difference(set(tree_list)))
    # папки, которые есть и там и там
    exact_folders = list(set(os_tree_list).intersection(set(tree_list)))  # SYNC_FOLDER\1\2...

    cloud.downloading_folders(download_folders)

    for folder in remove_folders:
        shutil.rmtree(get_os_path_by_cloud_path(folder))
        print(f'Папка {os.path.basename(folder)} удалена с пк')

    cloud.update_dir_on_pc(exact_folders)

@dataclass
class FileData:
    item_type: str
    item_name: str
    item_size: int
    item_modified: datetime


def list_files(path, clouds: [str]):
    # path в формате ROOT_FOLDER\...\folder
    if clouds:
        get_clouds = [v for k, v in CLOUDS.items() if k in clouds]
    else:
        get_clouds = CLOUDS.values()

    result = {os.path.basename(path): {} for _ in range(len(get_clouds))}
    for get_cloud in get_clouds:
        cloud = get_cloud('')

        if not cloud.check_root_folder():
            print('На облаке нет ранее синхронизированных папок')
            return

        file_data = cloud.list_files(path)
        if not file_data:
            return {}
        result[os.path.basename(path)][cloud.__class__.__name__] = cloud.list_files(path)

    return result

def get_os_path_by_cloud_path(clouds_path):
    sync_folders = get_and_update_sync_folders()
    sync_folder_this_last_folder = {os.path.basename(f): f for f in sync_folders}

    clouds_path = clouds_path.split(ROOT_FOLDER)[-1]
    if clouds_path.startswith(os.path.sep):
        clouds_path = clouds_path[1:]
    root_path = sync_folder_this_last_folder.get(clouds_path.split(os.path.sep)[0], None)
    if root_path:
        back_part = os.path.sep.join(clouds_path.split(os.path.sep)[1:])
        if back_part:
            back_part = os.path.sep + back_part
        return root_path + back_part
    # запрашиваем путь если не нашли в отслеживаемых
    from pyCloud import get_valid_folder_path
    return get_valid_folder_path(clouds_path)  # clouds_path всегда в таком случае просто название папки

    # from gui import CloudSyncApp
    # # Проверяем, существует ли активное приложение GUI
    # app = QApplication.instance()
    #
    # if app:
    #     # Если есть активное приложение, ищем его окна
    #     for widget in app.topLevelWidgets():
    #         if isinstance(widget, CloudSyncApp):
    #             # Вызываем метод для выбора папки из GUI
    #             return widget.choose_folder()
    #
    # # Если нет активного приложения, создаём временный экземпляр QApplication
    # app = QApplication([])  # Создание временного приложения
    # folder_path = QFileDialog.getExistingDirectory(None, "Select Folder")
    # app.quit()  # Закрываем временное приложение
    #
    # return folder_path if folder_path else '.'


if __name__ == '__main__':
    # save_sync_folders(r'D:\Document\SecCourseMATMEX\Python\PyCloud\SYNC_FOLDER')
    # print(get_sync_folders())
    # sync_locals_folders('dropbox')
    sync_folders(['google'])
    # list_files('SYNC_FOLDERS\\SYNC_FOLDER\\1\\1', 'google')
    # print(get_os_path_by_cloud_path('acb'))
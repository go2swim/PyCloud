import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
                             QLabel, QFileDialog, QCheckBox, QComboBox, QListWidget)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import QSize, Qt, QObject
from PyQt5.QtCore import QThread, pyqtSignal

from src.clouds_manager import (
    sync_folders,
    sync_locals_folders,
    get_and_update_sync_folders,
    save_sync_folders,
    remove_sync_folder,
    get_os_path_by_cloud_path
)

ICONS_FOLDER = "IconsForGui"
ICONS = {
    "active_drive": os.path.join(ICONS_FOLDER, "drive_icon.png"),
    "active_disk": os.path.join(ICONS_FOLDER, "disk_icon.png"),
    "active_dropbox": os.path.join(ICONS_FOLDER, "dropbox_icon.png"),
    "disabled_disk": os.path.join(ICONS_FOLDER, "disabled_disk.png"),
    "disabled_dropbox": os.path.join(ICONS_FOLDER, "disabled_dropbox.png"),
    "disabled_drive": os.path.join(ICONS_FOLDER, "disabled_drive.png"),

    "cloud_icon": os.path.join(ICONS_FOLDER, "cloud_icon"),
    "pc_icon": os.path.join(ICONS_FOLDER, "pc_icon"),
    "arrow_icon": os.path.join(ICONS_FOLDER, "arrow_icon"),

    "add_folder_icon": os.path.join(ICONS_FOLDER, "add_folder_icon"),
    "dirs_icon": os.path.join(ICONS_FOLDER, "dirs_icon.png"),

    "blurry_cloud": os.path.join(ICONS_FOLDER, "blurry_cloud.png"),
    "clear_cloud": os.path.join(ICONS_FOLDER, "clear_cloud.png"),
    "eagle": os.path.join(ICONS_FOLDER, "eagle.png"),
    "main_button": os.path.join(ICONS_FOLDER, "Ellipse 1.png"),
    "background_main_button": os.path.join(ICONS_FOLDER, "Ellipse 2.png"),
    "main_button_cut": os.path.join(ICONS_FOLDER, "main_button_cut.png"),

}

HEIGHT = 700
WIDTH = 700

class FolderChooser(QObject):
    folder_chosen = pyqtSignal(str)  # Сигнал для передачи выбранного пути обратно в поток

    def choose_folder(self):
        folder_path = QFileDialog.getExistingDirectory(None, "Select Folder")
        if folder_path:
            self.folder_chosen.emit(folder_path)
        else:
            self.folder_chosen.emit('.')

class CloudSyncApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('PyCloud')
        self.setGeometry(100, 100, WIDTH, HEIGHT)
        self.setStyleSheet("background-color: skyblue;")
        self.cloud_mode = 'cloud'  # По умолчанию синхронизация облака
        self.active_clouds = []
        self.folder_chooser = FolderChooser()

        self.folder_chooser = FolderChooser()

        self.initUI()

    def start_sync_worker(self, sync_type, active_clouds):
        # Создаем и запускаем поток
        self.sync_worker = SyncWorker(sync_type, active_clouds, self.folder_chooser)

        # Подключаем сигнал запроса выбора папки к методу выбора папки в главном потоке
        self.sync_worker.folder_requested.connect(self.folder_chooser.choose_folder)
        self.sync_worker.start()

    def initUI(self):
        layout = QVBoxLayout()

        # Верхняя панель с иконкой директорий
        top_layout = QHBoxLayout()

        self.show_folders_button = QPushButton()
        self.show_folders_button.setIcon(QIcon(ICONS['dirs_icon']))
        self.show_folders_button.setIconSize(QSize(100, 100))
        self.show_folders_button.clicked.connect(self.show_sync_folders)
        top_layout.addWidget(self.show_folders_button)

        self.folder_list = None
        self.add_folder_button = QPushButton()
        self.add_folder_button.setIcon(QIcon(ICONS['add_folder_icon']))
        self.add_folder_button.setIconSize(QSize(100, 100))
        self.add_folder_button.clicked.connect(self.add_folder)
        top_layout.addWidget(self.add_folder_button)

        # Добавляем лейбл PyCloud
        pycloud_label = QLabel("PyCloud")
        pycloud_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        top_layout.addWidget(pycloud_label)

        layout.addLayout(top_layout)

        # Кнопка SYNC
        self.sync_button = QPushButton()
        self.sync_button.setIcon(QIcon(ICONS['main_button_cut']))
        self.sync_button.setIconSize(QSize(200, 200))
        self.sync_button.clicked.connect(self.sync_action)
        layout.addWidget(self.sync_button)


        # Поле для выбора между PC и Cloud (пока будет заглушка)
        self.choose_cloud_or_pc_layout = QHBoxLayout()

        self.cloud_mode = "pc"
        self.cloud_button_counter = 0
        self.cloud_button = QPushButton()
        self.cloud_button.setIcon(QIcon(ICONS['cloud_icon']))
        self.cloud_button.setIconSize(QSize(100, 100))
        self.cloud_button.clicked.connect(self.toggle_sync_mode)
        self.choose_cloud_or_pc_layout.addWidget(self.cloud_button)

        arrow = QLabel(self)
        arrow.setPixmap(QPixmap(ICONS['arrow_icon']))
        arrow.setFixedSize(100, 100)
        self.choose_cloud_or_pc_layout.addWidget(arrow)

        self.pc_button = QPushButton()
        self.pc_button.setIcon(QIcon(ICONS['pc_icon']))
        self.pc_button.setIconSize(QSize(100, 100))
        self.pc_button.clicked.connect(self.toggle_sync_mode)
        self.choose_cloud_or_pc_layout.addWidget(self.pc_button)

        layout.addLayout(self.choose_cloud_or_pc_layout)



        # # Прогресс-бар (пока заглушка)
        # self.progress_bar_stub = QLabel("Progress Bar Stub")
        # self.progress_bar_stub.setStyleSheet("background-color: lightgray; height: 10px;")  # уменьшили высоту
        # self.progress_bar_stub.setFixedSize(600, 30)  # задали фиксированный размер
        # layout.addWidget(self.progress_bar_stub)

        # Иконки облаков (Drive, Disk, Dropbox)
        self.cloud_layout = QHBoxLayout()

        self.drive_button = QPushButton()
        self.drive_button.setIcon(QIcon(ICONS['disabled_drive']))
        self.drive_button.setIconSize(QSize(100, 100))
        self.drive_button.clicked.connect(lambda: self.toggle_cloud("drive", self.drive_button))
        self.cloud_layout.addWidget(self.drive_button)

        self.disk_button = QPushButton()
        self.disk_button.setIcon(QIcon(ICONS['disabled_disk']))
        self.disk_button.setIconSize(QSize(100, 100))
        self.disk_button.clicked.connect(lambda: self.toggle_cloud("disk", self.disk_button))
        self.cloud_layout.addWidget(self.disk_button)

        self.dropbox_button = QPushButton()
        self.dropbox_button.setIcon(QIcon(ICONS['disabled_dropbox']))
        self.dropbox_button.setIconSize(QSize(100, 100))
        self.dropbox_button.clicked.connect(lambda: self.toggle_cloud("dropbox", self.dropbox_button))
        self.cloud_layout.addWidget(self.dropbox_button)

        layout.addLayout(self.cloud_layout)

        self.setLayout(layout)

    def toggle_action(self):
        print('click')

    def toggle_sync_mode(self):
        name_of_buttons = ['cloud_icon', 'pc_icon']
        self.cloud_button_counter += 1
        self.cloud_button.setIcon(QIcon(ICONS[name_of_buttons[self.cloud_button_counter % 2]]))
        self.pc_button.setIcon(QIcon(ICONS[name_of_buttons[(self.cloud_button_counter + 1) % 2]]))
        self.change_mode()
        print(self.cloud_mode)

    def change_mode(self):
        if self.cloud_mode == 'pc':
            self.cloud_mode = 'cloud'
        else:
            self.cloud_mode = 'pc'
            if len(self.active_clouds) >= 1:
                for cloud in self.active_clouds:
                    if 'drive' in cloud:
                        self.drive_button.setIcon(QIcon(ICONS[f'disabled_drive']))
                        self.active_clouds.remove(cloud)
                    elif 'disk' in cloud:
                        self.disk_button.setIcon(QIcon(ICONS[f'disabled_disk']))
                        self.active_clouds.remove(cloud)
                    elif 'dropbox' in cloud:
                        self.dropbox_button.setIcon(QIcon(ICONS[f'disabled_dropbox']))
                        self.active_clouds.remove(cloud)


    def toggle_cloud(self, cloud_name, button):
        if self.cloud_mode == 'pc':
            if cloud_name in self.active_clouds:
                self.active_clouds.remove(cloud_name)
                button.setIcon(QIcon(ICONS[f'disabled_{cloud_name}']))
            else:
                if len(self.active_clouds) >= 1:
                    return
                else:
                    button.setIcon(QIcon(ICONS[f'active_{cloud_name}']))
                    self.active_clouds.append(cloud_name)
        else:  # В режиме Cloud можно выбирать несколько облаков
            if cloud_name in self.active_clouds:
                self.active_clouds.remove(cloud_name)
                button.setIcon(QIcon(ICONS[f'disabled_{cloud_name}']))
            else:
                self.active_clouds.append(cloud_name)
                button.setIcon(QIcon(ICONS[f'active_{cloud_name}']))

    def show_sync_folders(self):
        """Отображение списка папок на месте кнопки"""
        # if not hasattr(self, 'folder_list_widget'):  # Проверка, есть ли уже виджет списка папок
        # Создаем виджет списка папок
        self.folder_list_widget = QListWidget()
        self.folder_list_widget.setFixedSize(200, 150)
        self.folder_list_widget.move(self.show_folders_button.x(), self.show_folders_button.y())

        # Добавляем папки в список
        folders = get_and_update_sync_folders()
        self.folder_list_widget.addItems(list(map(lambda folder: os.path.basename(folder), folders)))

        # Задаем стили для списка (чтобы подходил под стиль твоего интерфейса)
        self.folder_list_widget.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #ccc;
            }
        """)

        # Действие при выборе папки
        self.folder_list_widget.itemClicked.connect(self.folder_selected)

        # Прячем кнопку, когда показываем список папок
        # self.show_folders_button.hide()

        # Показываем список папок
        self.folder_list_widget.show()
        # else:
        #     # Если список уже есть, то убираем его и возвращаем кнопку
        #     self.folder_list_widget.hide()
        #     self.show_folders_button.show()

    def folder_selected(self, item):
        """Обработчик выбора папки и удаление элемента списка."""
        # Получаем полный путь папки
        folder_path = get_os_path_by_cloud_path(item.text())

        # Удаляем папку из списка синхронизации
        remove_sync_folder(folder_path)

        # Удаляем элемент из списка отображения
        list_items = self.folder_list_widget.findItems(item.text(), Qt.MatchExactly)
        if list_items:
            item_index = self.folder_list_widget.row(list_items[0])
            self.folder_list_widget.takeItem(item_index)

        print(f"Папка {folder_path} удалена из списка синхронизации.")

    def sync_action(self):
        """Обработка нажатия на кнопку SYNC в зависимости от режима."""
        if not self.active_clouds:
            return

        self.sync_button.setEnabled(False)

        self.sync_worker = SyncWorker(self.cloud_mode, self.active_clouds, self.folder_chooser)

        # Подключаем сигнал запроса выбора папки к методу выбора папки в главном потоке
        self.sync_worker.folder_requested.connect(self.folder_chooser.choose_folder)
        self.sync_worker.start()

        self.sync_worker.finished.connect(self.on_sync_finished)

        # Запускаем поток
        self.sync_worker.start()

    def on_sync_finished(self):
        self.sync_button.setEnabled(True)
        print("Синхронизация завершена")

    def add_folder(self):
        """Открытие списка синхронизированных папок с возможностью добавления новой."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            save_sync_folders(folder_path)
            print(f"Добавлена папка: {folder_path}")

    def choose_folder(self):
        """Метод для выбора папки в GUI. Для использования сторонними методами"""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        return folder_path if folder_path else '.'

    def open_folder_dialog(self):
        """Этот метод вызывается в главном потоке для открытия диалога выбора папки."""
        folder_path = QFileDialog.getExistingDirectory(self, "Выберите папку для синхронизации")
        if folder_path:
            print(f"Путь к папке: {folder_path}")
        else:
            print("Папка не выбрана.")

class SyncWorker(QThread):
    finished = pyqtSignal()
    sync_type = None
    active_clouds = []
    folder_requested = pyqtSignal()

    def __init__(self, sync_type, active_clouds, folder_chooser):
        super().__init__()
        self.sync_type = sync_type
        self.active_clouds = active_clouds
        self.folder_chooser = folder_chooser
        self.selected_folder = None

        self.folder_chooser.folder_chosen.connect(self.on_folder_chosen)

    def run(self):
        # self.request_folder_selection.emit()

        actual_name = self.replace_on_actual_cloud_name(self.active_clouds)
        if self.sync_type == 'cloud':
            print(f"Синхронизируемся с облаками: {self.active_clouds}")
            sync_folders(actual_name)
        elif self.sync_type == 'pc':
            print(f"Синхронизируем файлы с облаков {self.active_clouds} на ПК")
            sync_locals_folders(actual_name[0])
        self.finished.emit()

    def replace_on_actual_cloud_name(self, active_clouds):
        actual_names_dict = {'drive': 'google', 'disk': 'yandex', 'dropbox': 'dropbox'}
        actual_name = active_clouds.copy()
        for i , name in enumerate(actual_name):
            actual_name[i] = actual_names_dict[name]

        return actual_name

    def on_folder_chosen(self, folder_path):
        # Получаем выбранную папку
        self.selected_folder = folder_path
        self.quit()  # Останавливаем поток после выбора папки

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CloudSyncApp()
    window.show()
    sys.exit(app.exec_())

import unittest
from unittest.mock import patch, MagicMock
from PyQt5.QtWidgets import QApplication
from gui import CloudSyncApp, ICONS, SyncWorker


class TestCloudSyncApp(unittest.TestCase):
    def setUp(self):
        app = QApplication([])
        self.cloud_sync_app = CloudSyncApp()
        self.cloud_sync_app.active_clouds = []
        self.cloud_sync_app.folder_list_widget = MagicMock()

    @patch("gui.QVBoxLayout")
    @patch("gui.QHBoxLayout")
    @patch("gui.QPushButton")
    @patch("gui.QLabel")
    @patch("gui.QIcon")
    @patch("gui.QPixmap")
    @patch("gui.QWidget.setLayout")
    def test_initUI(
        self,
        mock_setLayout,
        mock_QPixmap,
        mock_QIcon,
        mock_QLabel,
        mock_QPushButton,
        mock_QHBoxLayout,
        mock_QVBoxLayout,
    ):

        app = QApplication([])

        cloud_sync_app = CloudSyncApp()

        mock_QVBoxLayout.assert_called()
        mock_QHBoxLayout.assert_called()

        mock_QPushButton.assert_called()
        mock_QIcon.assert_called()
        mock_QLabel.assert_called()

        cloud_sync_app.show_folders_button.clicked.connect.assert_called()
        cloud_sync_app.add_folder_button.clicked.connect.assert_called()
        cloud_sync_app.sync_button.clicked.connect.assert_called()
        cloud_sync_app.cloud_button.clicked.connect.assert_called()
        cloud_sync_app.pc_button.clicked.connect.assert_called()
        mock_setLayout.assert_called_once()

        self.assertTrue(mock_QVBoxLayout.return_value.addLayout.called)
        self.assertTrue(mock_QVBoxLayout.return_value.addWidget.called)

        app.quit()

    @patch("builtins.print")
    @patch(
        "PyQt5.QtWidgets.QFileDialog.getExistingDirectory", return_value="/mock/path"
    )
    def test_add_folder(self, mock_file_dialog, mock_print):
        """Test the add_folder method that adds a folder."""
        app = QApplication([])

        window = CloudSyncApp()
        window.add_folder()

        mock_file_dialog.assert_called_once()

        mock_print.assert_called_with("Добавлена папка: /mock/path")

    @patch("PyQt5.QtWidgets.QListWidget")
    @patch("PyQt5.QtWidgets.QListWidget.addItems")
    @patch("PyQt5.QtWidgets.QListWidget.show")
    @patch(
        "src.clouds_manager.get_and_update_sync_folders",
        return_value=["/mock/path/folder1", "/mock/path/folder2"],
    )
    def test_show_sync_folders(
        self, mock_get_sync_folders, mock_show, mock_add_items, mock_folder_list_widget
    ):
        """Test the show_sync_folders method."""
        app = QApplication([])

        window = CloudSyncApp()
        window.show_sync_folders()

        mock_show.assert_called_once()

        mock_add_items.assert_called_once_with([])

    def tearDown(self):
        QApplication.quit()

    @patch("gui.QIcon")
    def test_toggle_action(self, mock_QIcon):

        with patch("builtins.print") as mocked_print:
            self.cloud_sync_app.toggle_action()
            mocked_print.assert_called_with("click")

    @patch("gui.QIcon")
    def test_toggle_sync_mode(self, mock_QIcon):

        self.cloud_sync_app.cloud_button = MagicMock()
        self.cloud_sync_app.pc_button = MagicMock()
        self.cloud_sync_app.cloud_mode = "pc"

        self.cloud_sync_app.toggle_sync_mode()

        mock_QIcon.assert_any_call(ICONS["cloud_icon"])
        mock_QIcon.assert_any_call(ICONS["pc_icon"])

        self.assertEqual(self.cloud_sync_app.cloud_mode, "cloud")

    @patch("gui.QIcon")
    def test_change_mode(self, mock_QIcon):

        self.cloud_sync_app.cloud_mode = "pc"
        self.cloud_sync_app.drive_button = MagicMock()
        self.cloud_sync_app.disk_button = MagicMock()
        self.cloud_sync_app.dropbox_button = MagicMock()

        self.cloud_sync_app.active_clouds = ["drive", "disk", "dropbox"]

        self.cloud_sync_app.change_mode()

        self.assertEqual(self.cloud_sync_app.cloud_mode, "cloud")

        self.cloud_sync_app.change_mode()
        self.assertEqual(self.cloud_sync_app.cloud_mode, "pc")

        mock_QIcon.assert_any_call(ICONS["disabled_drive"])
        mock_QIcon.assert_any_call(ICONS["disabled_dropbox"])

        self.assertEqual(len(self.cloud_sync_app.active_clouds), 1)

    @patch("gui.QIcon")
    def test_toggle_cloud(self, mock_QIcon):

        self.cloud_sync_app.cloud_mode = "pc"
        self.cloud_sync_app.drive_button = MagicMock()
        self.cloud_sync_app.active_clouds = []

        self.cloud_sync_app.toggle_cloud("drive", self.cloud_sync_app.drive_button)
        self.cloud_sync_app.drive_button.setIcon.assert_called_with(mock_QIcon())

        self.cloud_sync_app.toggle_cloud("drive", self.cloud_sync_app.drive_button)

        self.cloud_sync_app.cloud_mode = "cloud"

        self.cloud_sync_app.toggle_cloud("drive", self.cloud_sync_app.drive_button)
        mock_QIcon.assert_called_with(ICONS["active_drive"])
        self.assertIn("drive", self.cloud_sync_app.active_clouds)

        self.cloud_sync_app.toggle_cloud("drive", self.cloud_sync_app.drive_button)
        mock_QIcon.assert_called_with(ICONS["disabled_drive"])
        self.assertNotIn("drive", self.cloud_sync_app.active_clouds)

    @patch("gui.get_os_path_by_cloud_path")
    @patch("gui.remove_sync_folder")
    def test_folder_selected(
        self, mock_remove_sync_folder, mock_get_os_path_by_cloud_path
    ):

        item_mock = MagicMock()
        item_mock.text.return_value = "test_folder"

        mock_get_os_path_by_cloud_path.return_value = "/path/to/test_folder"

        self.cloud_sync_app.folder_list_widget.findItems.return_value = [item_mock]
        self.cloud_sync_app.folder_list_widget.row.return_value = 0

        self.cloud_sync_app.folder_selected(item_mock)

        mock_get_os_path_by_cloud_path.assert_called_once_with("test_folder")
        mock_remove_sync_folder.assert_called_once_with("/path/to/test_folder")
        self.cloud_sync_app.folder_list_widget.takeItem.assert_called_once_with(0)

    @patch("gui.SyncWorker")
    def test_sync_action(self, mock_SyncWorker):

        self.cloud_sync_app.active_clouds = ["drive"]
        self.cloud_sync_app.sync_button = MagicMock()

        self.cloud_sync_app.sync_action()

        self.cloud_sync_app.sync_button.setEnabled.assert_called_once_with(False)
        mock_SyncWorker.assert_called_once_with(
            self.cloud_sync_app.cloud_mode,
            self.cloud_sync_app.active_clouds,
            self.cloud_sync_app.folder_chooser,
        )

        sync_worker_instance = mock_SyncWorker.return_value
        sync_worker_instance.folder_requested.connect.assert_called_once_with(
            self.cloud_sync_app.folder_chooser.choose_folder
        )
        sync_worker_instance.start.assert_called()

    def test_on_sync_finished(self):

        self.cloud_sync_app.sync_button = MagicMock()

        self.cloud_sync_app.on_sync_finished()

        self.cloud_sync_app.sync_button.setEnabled.assert_called_once_with(True)

    @patch("gui.save_sync_folders")
    @patch("gui.QFileDialog.getExistingDirectory")
    def test_add_folder(self, mock_getExistingDirectory, mock_save_sync_folders):

        mock_getExistingDirectory.return_value = "/path/to/new_folder"

        self.cloud_sync_app.add_folder()

        mock_save_sync_folders.assert_called_once_with("/path/to/new_folder")
        print_output = "Добавлена папка: /path/to/new_folder"

        with patch("builtins.print") as mocked_print:
            self.cloud_sync_app.add_folder()
            mocked_print.assert_called_with(print_output)

    @patch("gui.QFileDialog.getExistingDirectory")
    def test_choose_folder(self, mock_getExistingDirectory):

        mock_getExistingDirectory.return_value = "/path/to/folder"

        result = self.cloud_sync_app.choose_folder()

        self.assertEqual(result, "/path/to/folder")

        mock_getExistingDirectory.return_value = None

        result = self.cloud_sync_app.choose_folder()

        self.assertEqual(result, ".")

    @patch("gui.QFileDialog.getExistingDirectory")
    def test_open_folder_dialog(self, mock_getExistingDirectory):

        mock_getExistingDirectory.return_value = "/path/to/folder"

        with patch("builtins.print") as mocked_print:
            self.cloud_sync_app.open_folder_dialog()
            mocked_print.assert_called_with("Путь к папке: /path/to/folder")

        mock_getExistingDirectory.return_value = None

        with patch("builtins.print") as mocked_print:
            self.cloud_sync_app.open_folder_dialog()
            mocked_print.assert_called_with("Папка не выбрана.")


class TestSyncWorker(unittest.TestCase):

    def setUp(self):
        self.folder_chooser_mock = MagicMock()
        self.folder_chooser_mock.folder_chosen = MagicMock()

        self.sync_worker = SyncWorker(
            "cloud", ["drive", "disk"], self.folder_chooser_mock
        )

    @patch("gui.sync_folders")
    @patch("gui.sync_locals_folders")
    def test_run_cloud_sync(self, mock_sync_locals_folders, mock_sync_folders):

        self.sync_worker.sync_type = "cloud"
        self.sync_worker.active_clouds = ["drive", "disk"]

        with patch.object(
            self.sync_worker, "finished", MagicMock()
        ) as mock_finished_signal:
            self.sync_worker.run()

            mock_sync_folders.assert_called_once_with(["google", "yandex"])
            mock_sync_locals_folders.assert_not_called()

            mock_finished_signal.emit.assert_called_once()

    @patch("gui.sync_folders")
    @patch("gui.sync_locals_folders")
    def test_run_pc_sync(self, mock_sync_locals_folders, mock_sync_folders):

        self.sync_worker.sync_type = "pc"
        self.sync_worker.active_clouds = ["drive"]

        with patch.object(
            self.sync_worker, "finished", MagicMock()
        ) as mock_finished_signal:
            self.sync_worker.run()

            mock_sync_locals_folders.assert_called_once_with("google")
            mock_sync_folders.assert_not_called()

            mock_finished_signal.emit.assert_called_once()

    def test_replace_on_actual_cloud_name(self):

        active_clouds = ["drive", "disk", "dropbox"]
        expected_names = ["google", "yandex", "dropbox"]

        actual_names = self.sync_worker.replace_on_actual_cloud_name(active_clouds)

        self.assertEqual(actual_names, expected_names)

    def test_on_folder_chosen(self):

        folder_path = "/path/to/folder"

        with patch.object(self.sync_worker, "quit", MagicMock()) as mock_quit:
            self.sync_worker.on_folder_chosen(folder_path)

            self.assertEqual(self.sync_worker.selected_folder, folder_path)

            mock_quit.assert_called_once()

    def test_folder_chooser_signal_connected(self):

        self.folder_chooser_mock.folder_chosen.connect.assert_called_once_with(
            self.sync_worker.on_folder_chosen
        )


if __name__ == "__main__":
    unittest.main()

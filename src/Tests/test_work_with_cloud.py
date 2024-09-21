import os
import unittest
from unittest.mock import patch, MagicMock, mock_open

from src.clouds_manager import (
    save_sync_folders,
    SAVE_SYNC_FILE,
    get_os_tree,
    sync_folders,
    sync_locals_folders,
    list_files,
    get_os_path_by_cloud_path,
)


class TestWorkThisCloud(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="D:/folder1\nD:/folder2\n")
    def test_save_sync_folders_existing_path(self, mock_file):
        save_sync_folders("D:/folder1")
        mock_file.assert_called_once_with(SAVE_SYNC_FILE, "r")
        mock_file().write.assert_not_called()

    @patch("builtins.open", new_callable=mock_open, read_data="D:/folder1\n")
    def test_save_sync_folders_new_path(self, mock_file):
        save_sync_folders("D:/folder2")
        mock_file().write.assert_called_with("D:/folder2\n")

    @patch("os.walk")
    def test_get_os_tree(self, mock_walk):
        mock_walk.return_value = [
            ("D:/folder", ["subfolder1", "subfolder2"], []),
            ("D:/folder/subfolder1", ["subsubfolder1"], []),
            ("D:/folder/subfolder2", [], []),
        ]

        result = get_os_tree("D:/folder")
        expected = ["subfolder1", "subfolder2", "subsubfolder1"]
        self.assertEqual(result, expected)

    @patch("builtins.print")
    @patch("src.clouds_manager.get_and_update_sync_folders")
    @patch("src.clouds_manager.get_os_tree")
    @patch("src.clouds_manager.CLOUDS")
    def test_sync_folders(
        self,
        mock_clouds,
        mock_get_os_tree,
        mock_get_and_update_sync_folders,
        mock_print,
    ):
        mock_get_and_update_sync_folders.return_value = ["D:/folder1", "D:/folder2"]
        mock_get_os_tree.side_effect = [
            ["subfolder1", "subfolder2"],  # For D:/folder1
            ["subfolderA", "subfolderB"],  # For D:/folder2
        ]

        mock_cloud_instance = MagicMock()

        mock_clouds.values.return_value = [lambda folder_full_path: mock_cloud_instance]
        mock_cloud_instance.get_cloud_tree.side_effect = [
            ["subfolder1", "subfolder3"],  # For D:/folder1
            ["subfolderA"],  # For D:/folder2
        ]

        with patch(
            "os.path.basename", side_effect=lambda path: os.path.split(path)[-1]
        ):
            sync_folders()

            mock_cloud_instance.check_upload.assert_called()
            mock_cloud_instance.get_cloud_tree.assert_called()
            mock_cloud_instance.update_dir_on_cloud.assert_called()
            mock_cloud_instance.remove_old_dir_on_cloud.assert_called()

            mock_cloud_instance.update_dir_on_cloud.assert_any_call(["folder1"])
            mock_cloud_instance.remove_old_dir_on_cloud.assert_any_call([])

    @patch("src.clouds_manager.CLOUDS")
    @patch("src.clouds_manager.get_and_update_sync_folders")
    @patch("src.clouds_manager.get_os_tree")
    @patch("src.clouds_manager.get_os_path_by_cloud_path")
    @patch("shutil.rmtree")
    def test_sync_locals_folders(
        self,
        mock_rmtree,
        mock_get_os_path_by_cloud_path,
        mock_get_os_tree,
        mock_get_and_update_sync_folders,
        mock_clouds,
    ):
        mock_cloud_instance = MagicMock()

        mock_clouds.__getitem__.return_value = (
            lambda folder_full_path: mock_cloud_instance
        )

        mock_cloud_instance.check_root_folder.return_value = True
        mock_cloud_instance.get_cloud_tree.return_value = None
        mock_cloud_instance.downloading_folders.return_value = None
        mock_cloud_instance.update_dir_on_pc.return_value = None

        mock_get_and_update_sync_folders.return_value = ["D:/folder1"]
        mock_get_os_tree.return_value = ["subfolder1", "subfolder2"]
        mock_get_os_path_by_cloud_path.return_value = "D:/folder1/subfolder2"

        tree_list = ["subfolder1", "subfolder3"]  # Данные с облака
        os_tree_list = ["subfolder1", "subfolder2"]  # Данные с локального диска

        mock_cloud_instance.get_cloud_tree.side_effect = (
            lambda root, tree_list_arg, _: tree_list_arg.extend(tree_list)
        )

        sync_locals_folders("yandex")

        mock_cloud_instance.check_root_folder.assert_called_once()
        mock_cloud_instance.get_cloud_tree.assert_called_once()
        mock_cloud_instance.downloading_folders.assert_called_once_with(
            ["subfolder3"]
        )  # На облаке, но нет на ПК
        mock_cloud_instance.update_dir_on_pc.assert_called_once_with(
            ["subfolder1"]
        )  # Синхронизация папок, которые есть и там, и там

        mock_rmtree.assert_any_call("D:/folder1/subfolder2")
        mock_get_os_path_by_cloud_path.assert_any_call("subfolder2")
        mock_get_os_path_by_cloud_path.assert_any_call("folder1")

    @patch("src.clouds_manager.CLOUDS")
    def test_list_files(self, mock_clouds):

        mock_cloud_instance = MagicMock()
        mock_clouds.__len__.return_value = 1

        mock_clouds.values.return_value = [lambda _: mock_cloud_instance]

        mock_cloud_instance.check_root_folder.return_value = True
        mock_cloud_instance.list_files.return_value = ["file1.txt", "file2.txt"]

        path = "ROOT_FOLDER\\folder"
        result = list_files(path, [])

        expected_result = {
            "folder": {
                mock_cloud_instance.__class__.__name__: ["file1.txt", "file2.txt"]
            }
        }

        self.assertEqual(result, expected_result)
        mock_cloud_instance.check_root_folder.assert_called_once()
        mock_cloud_instance.list_files.assert_any_call(path)

    @patch("src.clouds_manager.get_and_update_sync_folders")
    @patch("pyCloud.get_valid_folder_path")
    def test_get_os_path_by_cloud_path(
        self, mock_get_valid_folder_path, mock_get_and_update_sync_folders
    ):
        mock_get_and_update_sync_folders.return_value = ["D:/folder1", "D:/folder2"]
        mock_get_valid_folder_path.return_value = "D:/folder3"

        clouds_path = "SYNC_FOLDERS\\folder1\\subfolder"
        result = get_os_path_by_cloud_path(clouds_path)

        expected_result = "D:/folder1\\subfolder"

        self.assertEqual(result, expected_result)
        mock_get_and_update_sync_folders.assert_called_once()
        mock_get_valid_folder_path.assert_not_called()  # Не вызывается, так как путь найден

        clouds_path_not_found = "SYNC_FOLDERS\\folder3"
        result_not_found = get_os_path_by_cloud_path(clouds_path_not_found)
        self.assertEqual(result_not_found, "D:/folder3")
        mock_get_valid_folder_path.assert_called_once_with("folder3")

if __name__ == "__main__":
    unittest.main()

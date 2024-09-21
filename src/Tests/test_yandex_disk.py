import os
import unittest
import datetime
from unittest import mock
from unittest.mock import patch, MagicMock, mock_open
import requests

from src.Yandex import yandex_disk
from src.Yandex.yandex_disk import YandexDisk, URL


class TestYandexDisk(unittest.TestCase):

    @patch("src.Yandex.yandex_disk.YandexHeadersManager")
    def setUp(self, mock_headers):
        self.disk = YandexDisk("test_dir", "/path/to/test")
        mock_headers.token = "token"
        self.headers = self.disk.headers

    @patch("src.Yandex.yandex_disk.requests.get")
    def test_handle_response_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"{}"
        mock_response.json.return_value = {"result": "success"}
        result = self.disk.handle_response(mock_response)
        self.assertEqual(result, {"result": "success"})

    @patch("src.Yandex.yandex_disk.requests.get")
    def test_handle_response_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.content = b'{"message": "Bad request"}'
        mock_response.json.return_value = {"message": "Bad request"}
        with patch("builtins.print") as mocked_print:
            self.disk.handle_response(mock_response)
            mocked_print.assert_called_with("Ошибка 400: Bad request")

    @patch("src.Yandex.yandex_disk.requests.put")
    def test_create_folder_success(self, mock_put):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_put.return_value = mock_response
        with patch.object(self.disk, "handle_response") as mock_handle_response:
            self.disk.create_folder("test_folder")
            mock_handle_response.assert_called_once_with(mock_response)

    @patch("src.Yandex.yandex_disk.requests.put")
    def test_create_folder_request_exception(self, mock_put):
        mock_put.side_effect = requests.exceptions.RequestException(
            "Error creating folder"
        )
        with patch("builtins.print") as mocked_print:
            self.disk.create_folder("test_folder")
            mocked_print.assert_called_with(
                "Ошибка при создании папки: Error creating folder"
            )

    @patch("src.Yandex.yandex_disk.requests.get")
    @patch("src.Yandex.yandex_disk.requests.put")
    def test_upload_file_success(self, mock_put, mock_get):
        mock_response_get = MagicMock()
        mock_response_get.status_code = 200
        mock_response_get.json.return_value = {"href": "https://upload_link"}
        mock_get.return_value = mock_response_get

        mock_response_put = MagicMock()
        mock_response_put.status_code = 201
        mock_put.return_value = mock_response_put

        with patch(
            "builtins.open", unittest.mock.mock_open(read_data="file_content")
        ) as mock_file:
            with patch.object(self.disk, "handle_response") as mock_handle_response:
                self.disk.upload_file("local_file.txt", "remote_file.txt")
                mock_get.assert_called_once_with(
                    f"https://cloud-api.yandex.net/v1/disk/resources/upload?path=remote_file.txt&overwrite=False",
                    headers=self.headers,
                )
                mock_put.assert_called_once()
                mock_handle_response.assert_called_with(mock_response_put)

    @patch("src.Yandex.yandex_disk.requests.get")
    def test_upload_file_request_exception(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException(
            "Error getting upload link"
        )
        with patch("builtins.print") as mocked_print:
            self.disk.upload_file("local_file.txt", "remote_file.txt")
            mocked_print.assert_called_with(
                "Ошибка при загрузке файла 'local_file.txt': Error getting upload link"
            )

    @patch("src.Yandex.yandex_disk.requests.delete")
    def test_delete(self, mock_delete):
        with patch("builtins.print") as mocked_print:
            self.disk.delete("/test")
            mocked_print.assert_called_with(f"Ресурс '/test' успешно удален.")

    @patch("src.Yandex.yandex_disk.requests.get")
    def test_download_file_success(self, mock_get):
        mock_response_get = MagicMock()
        mock_response_get.status_code = 200
        mock_response_get.json.return_value = {"href": "https://download_link"}
        mock_get.return_value = mock_response_get

        mock_download_response = MagicMock()
        mock_download_response.iter_content = lambda chunk_size: [b"file_content"]
        mock_get.return_value = mock_download_response

        with patch("builtins.open", mock_open()) as mock_file:
            with patch.object(self.disk, "handle_response") as mock_handle_response:
                self.disk.download("file.txt", "/save_path", is_folder=False)
                mock_handle_response.assert_called_once()
                mock_file.assert_called_once()

    @patch("os.remove")
    @patch("src.Yandex.yandex_disk.requests.get")
    def test_download_folder_success(self, mock_get, remove_mock):
        mock_response_get = MagicMock()
        mock_response_get.status_code = 200
        mock_response_get.json.return_value = {"href": "https://download_link"}
        mock_get.return_value = mock_response_get

        mock_download_response = MagicMock()
        mock_download_response.content = b"archive_content"
        mock_get.return_value = mock_download_response

        with patch("builtins.open", mock_open()) as mock_file:
            with patch("src.Yandex.yandex_disk.zipfile.ZipFile") as mock_zipfile:
                with patch.object(self.disk, "handle_response") as mock_handle_response:
                    self.disk.download("folder", "/save_path", is_folder=True)

                    mock_handle_response.assert_called()
                    mock_file.assert_called_once_with("/save_path\\archive.zip", "wb")
                    mock_zipfile.assert_called_once_with("/save_path\\archive.zip", "r")

                    remove_mock.assert_called_once_with("/save_path\\archive.zip")

    @patch.object(YandexDisk, "download")
    @patch("os.path.exists", return_value=False)
    def test_downloading_folders(self, mock_exists, mock_download):
        download_folders = ["folder1", "folder2/subfolder"]

        with patch(
            "src.clouds_manager.get_os_path_by_cloud_path",
            side_effect=lambda x: f"/local_path/{x}",
        ):
            self.disk.downloading_folders(download_folders)

            self.assertEqual(mock_download.call_count, 2)

    @patch("src.Yandex.yandex_disk.requests.get")
    def test_list_files_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "_embedded": {
                "items": [
                    {
                        "name": "file1.txt",
                        "type": "file",
                        "size": 12345,
                        "modified": "2023-01-01T12:00:00Z",
                    },
                    {
                        "name": "folder1",
                        "type": "dir",
                        "modified": "2023-01-02T12:00:00Z",
                    },
                ]
            }
        }
        mock_get.return_value = mock_response

        with patch("src.clouds_manager.FileData") as mock_filedata:
            with patch.object(
                self.disk, "handle_response", return_value=mock_response.json()
            ):
                result = self.disk.list_files("/some_path")

                self.assertEqual(len(result), 2)
                mock_filedata.assert_any_call(
                    item_type="FILE",
                    item_name="file1.txt",
                    item_size=12345,
                    item_modified=mock.ANY,
                )
                mock_filedata.assert_any_call(
                    item_type="DIR",
                    item_name="folder1",
                    item_size=None,
                    item_modified=mock.ANY,
                )

    @patch("src.Yandex.yandex_disk.requests.get")
    def test_check_root_folder(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "_embedded": {
                "items": [
                    {"name": "test_root", "type": "dir"},
                    {"name": "other_folder", "type": "dir"},
                ]
            }
        }
        mock_get.return_value = mock_response

        with patch.object(
            self.disk, "handle_response", return_value=mock_response.json()
        ):
            result = self.disk.check_root_folder()
            self.assertFalse(result)

    @patch.object(YandexDisk, "create_folder")
    @patch.object(YandexDisk, "check_root_folder", return_value=False)
    @patch("src.Yandex.yandex_disk.requests.get")
    def test_check_upload(self, mock_get, mock_check_root_folder, mock_create_folder):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "_embedded": {"items": [{"name": "existing_folder", "type": "dir"}]}
        }
        mock_get.return_value = mock_response

        with patch.object(
            self.disk, "handle_response", return_value=mock_response.json()
        ):
            self.disk.check_upload()

        mock_create_folder.assert_any_call(f"{self.disk.ROOT_FOLDER}")
        mock_create_folder.assert_any_call(
            f"{self.disk.ROOT_FOLDER}/{self.disk.dir_name}"
        )

    @patch("src.Yandex.yandex_disk.requests.get")
    def test_get_cloud_tree(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "_embedded": {
                "items": [
                    {"name": "subfolder1", "type": "dir"},
                    {"name": "subfolder2", "type": "dir"},
                ]
            }
        }
        mock_get.return_value = mock_response

        tree_list = []
        folder_name = "root_folder"

        with patch.object(
            self.disk,
            "handle_response",
            side_effect=[
                mock_response.json(),
                {"_embedded": {"items": []}},
                {"_embedded": {"items": []}},
            ],
        ):
            self.disk.get_cloud_tree(folder_name, tree_list, "")

        self.assertIn(f"root_folder{os.path.sep}subfolder1", tree_list)
        self.assertIn(f"root_folder{os.path.sep}subfolder2", tree_list)
        self.assertEqual(len(tree_list), 2)

    @patch.object(YandexDisk, "create_folder")
    @patch.object(YandexDisk, "upload_file")
    @patch("os.listdir")
    @patch("os.path.isfile", return_value=True)
    def test_upload_dir_to_cloud(
        self, mock_isfile, mock_listdir, mock_upload_file, mock_create_folder
    ):

        upload_folders = ["folder1", "folder2/subfolder"]

        mock_listdir.side_effect = [["file1.txt", "file2.txt"], ["file3.txt"]]

        self.disk.upload_dir_on_cloud(upload_folders)

        mock_create_folder.assert_any_call(f"{self.disk.ROOT_FOLDER}/folder1")
        mock_create_folder.assert_any_call(f"{self.disk.ROOT_FOLDER}/folder2/subfolder")

        mock_upload_file.assert_any_call(
            "folder1\\file1.txt", f"{self.disk.ROOT_FOLDER}/folder1/file1.txt"
        )
        mock_upload_file.assert_any_call(
            "folder1\\file2.txt", f"{self.disk.ROOT_FOLDER}/folder1/file2.txt"
        )
        mock_upload_file.assert_any_call(
            "folder2/subfolder\\file3.txt",
            f"{self.disk.ROOT_FOLDER}/folder2/subfolder/file3.txt",
        )

        self.assertEqual(mock_upload_file.call_count, 3)

    @patch("os.listdir")
    @patch("os.path.isfile", return_value=True)
    @patch("src.Yandex.yandex_disk.requests.get")
    def test_get_os_and_clouds_files(self, mock_get, mock_isfile, mock_listdir):
        mock_listdir.return_value = ["file1.txt", "file2.txt"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "_embedded": {
                "items": [
                    {"name": "file1.txt", "type": "file", "md5": "abc123"},
                    {"name": "file3.txt", "type": "file", "md5": "def456"},
                ]
            }
        }
        mock_get.return_value = mock_response

        folder_dir = "test_folder"
        full_path = "/local/test_folder"

        with patch.object(
            self.disk, "handle_response", return_value=mock_response.json()
        ):
            os_files, cloud_files = self.disk.get_os_and_clouds_files(
                folder_dir, full_path
            )

        mock_listdir.assert_called_once_with(full_path)
        self.assertEqual(os_files, ["file1.txt", "file2.txt"])

        mock_get.assert_called_once_with(
            f"{URL}?path=/{self.disk.ROOT_FOLDER}/test_folder", headers=self.headers
        )
        self.assertEqual(len(cloud_files), 2)
        self.assertEqual(cloud_files[0]["name"], "file1.txt")
        self.assertEqual(cloud_files[1]["name"], "file3.txt")

    @patch("os.path.getmtime", return_value=1609459200)
    @patch("builtins.open", new_callable=mock_open, read_data=b"test content")
    @patch("hashlib.md5")
    def test_get_data_for_comparison(self, mock_md5, mock_open, mock_getmtime):

        mock_md5.return_value.hexdigest.return_value = "abc123"

        os_path_file = "/local/test_folder/file1.txt"
        cloud_file = {
            "name": "file1.txt",
            "modified": "2021-01-01T12:00:00+00:00",
            "md5": "abc123",
        }

        os_modified_time, cloud_modified_time, os_file_md5, cloud_file_md5 = (
            self.disk.get_data_for_comparison(os_path_file, cloud_file)
        )

        expected_os_time = datetime.datetime(
            2021, 1, 1, 0, 0, tzinfo=datetime.datetime.now().astimezone().tzinfo
        )
        expected_cloud_time = datetime.datetime(
            2021, 1, 1, 12, 0, tzinfo=datetime.timezone.utc
        )

        self.assertEqual(cloud_modified_time, expected_cloud_time)

        mock_open.assert_called_once_with(os_path_file, "rb")
        self.assertEqual(os_file_md5, "abc123")
        self.assertEqual(cloud_file_md5, "abc123")

    @patch.object(yandex_disk.YandexDisk, "get_os_and_clouds_files")
    @patch.object(yandex_disk.YandexDisk, "get_data_for_comparison")
    @patch.object(yandex_disk.YandexDisk, "upload_file")
    @patch.object(yandex_disk.YandexDisk, "delete")
    def test_update_dir_on_cloud(
        self,
        mock_delete,
        mock_upload_file,
        mock_get_data_for_comparison,
        mock_get_os_and_clouds_files,
    ):
        mock_get_os_and_clouds_files.return_value = (
            ["file1.txt", "file2.txt", "file3.txt"],
            [
                {
                    "name": "file1.txt",
                    "path": "/path/file1.txt",
                    "md5": "abc123",
                    "modified": "2021-01-01T12:00:00+00:00",
                },
                {
                    "name": "file4.txt",
                    "path": "/path/file4.txt",
                    "md5": "def456",
                    "modified": "2021-01-01T12:00:00+00:00",
                },
            ],
        )

        mock_get_data_for_comparison.side_effect = [
            (
                datetime.datetime(2024, 1, 1, 0, 0),
                datetime.datetime(2021, 1, 1, 12, 0),
                "abc123",
                "abc123",
            )
        ]

        exact_folders = ["test_folder"]

        self.disk.update_dir_on_cloud(exact_folders)

        mock_upload_file.assert_any_call(
            os.path.join("\\test_folder", "file1.txt"), "/path/file1.txt", replace=True
        )

        mock_delete.assert_called_once_with("/path/file4.txt")

    @patch("src.clouds_manager.get_os_path_by_cloud_path", return_value="test_folder")
    @patch.object(yandex_disk.YandexDisk, "get_os_and_clouds_files")
    @patch.object(yandex_disk.YandexDisk, "get_data_for_comparison")
    @patch.object(yandex_disk.YandexDisk, "download")
    @patch("os.remove")
    def test_update_dir_on_pc(
        self,
        mock_remove,
        mock_download,
        mock_get_data_for_comparison,
        mock_get_os_and_clouds_files,
        _,
    ):
        mock_get_os_and_clouds_files.return_value = (
            ["file1.txt", "file2.txt"],
            [
                {
                    "name": "file1.txt",
                    "path": "/path/file1.txt",
                    "md5": "abc123",
                    "modified": "2023-01-01T12:00:00+00:00",
                },
                {
                    "name": "file3.txt",
                    "path": "/path/file3.txt",
                    "md5": "def456",
                    "modified": "2023-01-01T12:00:00+00:00",
                },
            ],
        )

        mock_get_data_for_comparison.side_effect = [
            (
                datetime.datetime(2023, 1, 1, 0, 0),
                datetime.datetime(2023, 1, 1, 12, 0),
                "abc123",
                "abc123",
            )
        ]

        exact_folders = ["test_folder"]

        self.disk.update_dir_on_pc(exact_folders)

        mock_download.assert_any_call("path/file1.txt", "test_folder", is_folder=False)

        mock_remove.assert_called_once_with("test_folder\\file2.txt")

    def test_format_datetime(self):

        iso_date = "2023-01-01T12:00:00Z"
        expected_date = datetime.datetime(
            2023, 1, 1, 12, 0, tzinfo=datetime.timezone.utc
        )

        result = yandex_disk.format_datetime(iso_date)

        assert result == expected_date


if __name__ == "__main__":
    unittest.main()

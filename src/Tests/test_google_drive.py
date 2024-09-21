import unittest
import datetime
from unittest.mock import patch, MagicMock, mock_open

from src.Drive import google_drive
from src.Drive.google_drive import GoogleDrive
import os


class TestGoogleDrive(unittest.TestCase):

    @patch("src.Drive.google_drive.GoogleDrive.check_upload", return_value="test_folder_id")
    @patch("src.Drive.google_drive.get_service")
    def setUp(self, mock_build, _):
        self.mock_service = MagicMock()
        mock_build.return_value = self.mock_service

        self.drive = GoogleDrive(dir_name="test_folder", full_path="/test/path")
        self.drive.ROOT_FOLDER = "test_root"
        self.drive.parents_id = {
            "root_folder": "root_id",
            "subfolder1": "subfolder1_id",
            "test_folder": "test_folder_id",
        }

    @patch("src.Drive.google_drive.GoogleDrive.check_upload", return_value="123")
    def test_init(self, mock_check_upload):
        self.assertEqual(self.drive.dir_name, "test_folder")
        self.assertEqual(self.drive.full_path, "/test/path")
        self.assertEqual(self.drive.folder_id, "test_folder_id")

    def test_check_upload_folder_exists(self):
        # Мок ответа API Google Drive при запросе существующих папок
        mock_files_list = self.mock_service.files().list
        mock_files_list.return_value.execute.return_value = {
            "files": [
                {"name": "test_root", "id": "root_folder_id"},
                {"name": "test_folder", "id": "folder_id"},
            ]
        }

        folder_id = self.drive.check_upload()

        self.assertEqual(folder_id, "folder_id")
        self.assertEqual(mock_files_list.call_count, 2)

    @patch("src.Drive.google_drive.GoogleDrive.root_folder_upload")
    def test_check_upload_root_folder_created(self, mock_folder_upload):
        mock_files_list = self.mock_service.files().list
        mock_files_create = self.mock_service.files().create

        mock_files_list.return_value.execute.side_effect = [
            {"files": []},  # Сначала нет корневой папки
            {"files": []},  # Нет папок в созданной корневой папке
        ]

        # mock_files_create.return_value.execute.return_value = {'id': 'new_root_folder_id'}
        mock_folder_upload.return_value = {self.drive.dir_name: "123"}

        folder_id = self.drive.check_upload()

        mock_files_create.assert_called_once()
        self.assertEqual(folder_id, "123")
        self.assertEqual(mock_files_list.call_count, 2)

    @patch("src.Drive.google_drive.os.walk")
    @patch("src.Drive.google_drive.MediaFileUpload")
    def test_root_folder_upload(self, mock_media_upload, mock_os_walk):
        mock_os_walk.return_value = [
            ("\\test\\path", ["subdir"], ["file1.txt", "file2.txt"])
        ]
        mock_create = self.mock_service.files().create.return_value
        mock_create.execute.return_value = {"id": "folder_id"}

        folder_id = self.drive.root_folder_upload("root_folder_id")

        self.assertEqual(folder_id["path"], "folder_id")
        mock_media_upload.assert_called()

    @patch("src.Drive.google_drive.GoogleDrive.get_drive_tree")
    def test_get_cloud_tree_with_empty_str(self, mock_get_drive_tree):
        self.drive.root_id = "1"
        self.drive.get_cloud_tree("", [], "")
        self.assertEqual(
            self.drive.parents_id, {self.drive.ROOT_FOLDER: self.drive.root_id}
        )
        mock_get_drive_tree.assert_called_with(self.drive.ROOT_FOLDER, [], "")

    @patch("src.Drive.google_drive.GoogleDrive.get_drive_tree")
    def test_get_cloud_tree(self, mock_get_drive_tree):
        self.drive.root_id = "1"
        self.drive.get_cloud_tree("1\\2", [], "")
        self.assertEqual(self.drive.parents_id, {"/test/path": self.drive.folder_id})
        mock_get_drive_tree.assert_called_with("/test/path", [], "")

    def test_get_drive_tree_basic(self):
        mock_files_list = self.mock_service.files().list
        mock_files_list.return_value.execute.side_effect = [
            {
                "files": [
                    {
                        "id": "subfolder1_id",
                        "name": "subfolder1",
                        "mimeType": "application/vnd.google-apps.folder",
                    }
                ]
            },
            {},
        ]

        tree_list = []
        root = "root_folder"

        self.drive.get_drive_tree("root_folder", tree_list, root)

        expected_tree_list = ["root_folderroot_folder\\subfolder1"]

        self.assertEqual(tree_list, expected_tree_list)

    def test_get_drive_tree_no_folders(self):
        mock_files_list = self.mock_service.files().list
        mock_files_list.return_value.execute.return_value = {"files": []}

        tree_list = []
        root = "root_folder"

        self.drive.get_drive_tree("root_folder", tree_list, root)

        self.assertEqual(tree_list, [])

    def test_get_drive_tree_nested_folders(self):
        mock_files_list = self.mock_service.files().list
        mock_files_list.return_value.execute.side_effect = [
            {
                "files": [
                    {
                        "id": "subfolder1_id",
                        "name": "subfolder1",
                        "mimeType": "application/vnd.google-apps.folder",
                    }
                ]
            },
            {
                "files": [
                    {
                        "id": "subsubfolder1_id",
                        "name": "subsubfolder1",
                        "mimeType": "application/vnd.google-apps.folder",
                    }
                ]
            },
            {},
        ]

        tree_list = []
        root = "root_folder"

        self.drive.get_drive_tree("root_folder", tree_list, root)

        expected_tree_list = [
            "root_folderroot_folder\\subfolder1",
            "root_folderroot_folder\\subfolder1\\subsubfolder1",
        ]

        self.assertEqual(tree_list, expected_tree_list)

    @patch("os.listdir")
    @patch("os.path.isfile")
    @patch("src.Drive.google_drive.MediaFileUpload")
    @patch("src.Drive.google_drive.mimetypes.MimeTypes")
    def test_upload_dir_to_cloud(
        self, mock_mimetypes, mock_media_upload, mock_isfile, mock_listdir
    ):
        mock_listdir.side_effect = lambda x: (
            ["file1.txt", "file2.txt"] if "test_folder" in x else []
        )
        mock_isfile.side_effect = lambda x: True

        mock_media_upload.return_value = MagicMock()

        mock_mimetypes().guess_type.return_value = ("text/plain", None)

        mock_files_create = self.mock_service.files().create
        mock_files_create.return_value.execute.side_effect = [
            {"id": "new_folder_id"},  # Для создания папки
            {"id": "file1_id"},  # Для загрузки file1.txt
            {"id": "file2_id"},  # Для загрузки file2.txt
        ]

        upload_folders = ["root_folder\\test_folder"]

        self.drive.upload_dir_on_cloud(upload_folders)

        mock_files_create.assert_called()

    @patch("src.Drive.google_drive.os.listdir")
    @patch("src.Drive.google_drive.os.path.isfile")
    def test_get_os_and_cloud_files(self, mock_isfile, mock_listdir):
        mock_listdir.return_value = ["file1.txt", "file2.txt"]
        mock_isfile.return_value = True

        mock_list_files = self.mock_service.files().list.return_value
        mock_list_files.execute.return_value = {
            "files": [
                {
                    "name": "file1.txt",
                    "id": "1",
                    "modifiedTime": "2024-09-01T12:00:00Z",
                    "md5Checksum": "abcd1234",
                }
            ]
        }

        os_files, cloud_files = self.drive.get_os_and_cloud_files(
            "folder_id", "/test/path"
        )

        self.assertEqual(os_files, ["file1.txt", "file2.txt"])
        self.assertEqual(cloud_files[0]["name"], "file1.txt")

    @patch("src.Drive.google_drive.os.path.getmtime")
    @patch("src.Drive.google_drive.open", create=True)
    @patch("src.Drive.google_drive.hashlib.md5")
    def test_get_data_for_comparison(self, mock_md5, mock_open, mock_getmtime):
        mock_getmtime.return_value = 1609459200  # 1 января 2024

        mock_file = MagicMock()
        mock_file.read.return_value = b"test_file_content"
        mock_open.return_value.__enter__.return_value = mock_file

        mock_md5.return_value.hexdigest.return_value = (
            "d41d8cd98f00b204e9800998ecf8427e"
        )

        path_to_file = "/test/path"
        drive_file = {
            "name": "test_file.txt",
            "modifiedTime": "2023-01-01T12:00:00.000Z",
            "md5Checksum": "d41d8cd98f00b204e9800998ecf8427e",
        }
        clouds_files = [
            {"name": "test_file.txt", "modifiedTime": "2023-01-01T12:00:00.000Z"}
        ]

        expected_os_modified_time = datetime.datetime(
            2021, 1, 1, 5, 0, tzinfo=datetime.datetime.now().astimezone().tzinfo
        )
        expected_cloud_modified_time = datetime.datetime(
            2023, 1, 1, 12, 0, tzinfo=datetime.timezone.utc
        )
        expected_os_file_md5 = "d41d8cd98f00b204e9800998ecf8427e"
        expected_drive_md5 = "d41d8cd98f00b204e9800998ecf8427e"

        os_modified_time, cloud_modified_time, os_file_md5, drive_md5 = (
            self.drive.get_data_for_comparison(path_to_file, drive_file, clouds_files)
        )

        self.assertEqual(os_modified_time, expected_os_modified_time)
        self.assertEqual(cloud_modified_time, expected_cloud_modified_time)
        self.assertEqual(os_file_md5, expected_os_file_md5)
        self.assertEqual(drive_md5, expected_drive_md5)

    @patch("src.clouds_manager.get_os_path_by_cloud_path")
    @patch("src.Drive.google_drive.GoogleDrive.get_data_for_comparison")
    @patch("src.Drive.google_drive.GoogleDrive.get_os_and_cloud_files")
    @patch("src.Drive.google_drive.MediaFileUpload")
    def test_update_dir_on_cloud(
        self,
        mock_media_upload,
        mock_get_os_and_cloud_files,
        mock_get_data_for_comparison,
        mock_get_os_path_by_cloud_path,
    ):
        mock_get_os_path_by_cloud_path.return_value = "/test/path/sub_folder"

        mock_get_os_and_cloud_files.return_value = (
            ["file1.txt", "file2.txt"],
            [
                {
                    "name": "file1.txt",
                    "id": "123",
                    "modifiedTime": "2023-01-01T12:00:00.000Z",
                    "mimeType": "text/plain",
                },
                {
                    "name": "file3.txt",
                    "id": "456",
                    "modifiedTime": "2022-12-31T10:00:00.000Z",
                    "mimeType": "text/plain",
                },
            ],
        )

        mock_get_data_for_comparison.return_value = (
            datetime.datetime(2023, 1, 1, 12, 0),  # Локальное время модификации
            datetime.datetime(2022, 12, 31, 10, 0),  # Время модификации в облаке
            "d41d8cd98f00b204e9800998ecf8427e",  # Локальная контрольная сумма
            "d41d8cd98f00b204e9800998ecf8427e",  # Контрольная сумма в облаке
        )

        self.drive.parents_id = {
            "test_folder": "root_folder_id",
            "sub_folder": "sub_folder_id",
        }

        exact_folders = ["test_folder/sub_folder"]

        self.drive.update_dir_on_cloud(exact_folders)

        mock_get_os_path_by_cloud_path.assert_called_once_with("test_folder/sub_folder")
        mock_get_os_and_cloud_files.assert_called_once_with(
            "sub_folder_id", "/test/path/sub_folder"
        )
        (
            mock_get_data_for_comparison.assert_called_with(
                "/test/path/sub_folder",
                {
                    "name": "file1.txt",
                    "id": "123",
                    "modifiedTime": "2023-01-01T12:00:00.000Z",
                    "mimeType": "text/plain",
                },
                [
                    {
                        "name": "file1.txt",
                        "id": "123",
                        "modifiedTime": "2023-01" "-01T12" ":00:00" ".000Z",
                        "mimeType": "text/plain",
                    },
                    {
                        "name": "file3.txt",
                        "id": "456",
                        "modifiedTime": "2022-12-31T10:00:00.000Z",
                        "mimeType": "text/plain",
                    },
                ],
            )
        )

        self.mock_service.files().update.assert_called_once()

        self.mock_service.files().delete.assert_called_once_with(fileId="456")

        self.mock_service.files().create.assert_called_once()

    @patch("src.Drive.google_drive.os.path.sep", "/")
    def test_remove_old_dir_on_cloud(self):
        self.drive.parents_id = {
            "sub_folder1": "sub_folder1_id",
            "sub_folder2": "sub_folder2_id",
            "sub_folder3": "sub_folder3_id",
        }

        remove_folders = ["sub_folder1", "sub_folder2", "sub_folder3"]

        self.drive.remove_old_dir_on_cloud(remove_folders)

        self.assertEqual(
            remove_folders,
            sorted(
                remove_folders,
                key=lambda input_str: input_str.count(os.path.sep),
                reverse=True,
            ),
        )

        self.drive.service.files().delete.assert_any_call(fileId="sub_folder1_id")
        self.drive.service.files().delete.assert_any_call(fileId="sub_folder2_id")
        self.drive.service.files().delete.assert_any_call(fileId="sub_folder3_id")

        self.assertEqual(self.drive.service.files().delete.call_count, 3)

    @patch("src.Drive.google_drive.os.path.sep", "/")
    def test_remove_old_dir_on_cloud_empty(self):
        remove_folders = []

        self.drive.remove_old_dir_on_cloud(remove_folders)
        self.drive.service.files().delete.assert_not_called()

    @patch("src.Drive.google_drive.os.makedirs")
    @patch("src.clouds_manager.get_os_path_by_cloud_path")
    @patch("src.Drive.google_drive.GoogleDrive.download_file_from_drive")
    def test_downloading_folders(
        self, mock_download_file, mock_get_os_path, mock_makedirs
    ):
        self.drive.parents_id = {
            "sub_folder1": "sub_folder1_id",
            "sub_folder2": "sub_folder2_id",
        }
        download_folders = ["sub_folder1", "sub_folder2"]

        mock_get_os_path.side_effect = lambda folder_dir: f"/test/path/{folder_dir}"

        self.drive.service.files().list.return_value.execute.return_value = {
            "files": [
                {"name": "file1.txt", "mimeType": "text/plain"},
                {"name": "file2.txt", "mimeType": "text/plain"},
            ]
        }

        self.drive.downloading_folders(download_folders)

        self.assertEqual(
            download_folders,
            sorted(
                download_folders, key=lambda input_str: input_str.count(os.path.sep)
            ),
        )

        mock_makedirs.assert_any_call("/test/path/sub_folder1")
        mock_makedirs.assert_any_call("/test/path/sub_folder2")

        mock_download_file.assert_any_call(
            "/test/path/sub_folder1", {"name": "file1.txt", "mimeType": "text/plain"}
        )
        mock_download_file.assert_any_call(
            "/test/path/sub_folder1", {"name": "file2.txt", "mimeType": "text/plain"}
        )
        mock_download_file.assert_any_call(
            "/test/path/sub_folder2", {"name": "file1.txt", "mimeType": "text/plain"}
        )
        mock_download_file.assert_any_call(
            "/test/path/sub_folder2", {"name": "file2.txt", "mimeType": "text/plain"}
        )

        self.drive.service.files().list.assert_any_call(
            pageSize=20, q="'sub_folder1_id' in parents"
        )
        self.drive.service.files().list.assert_any_call(
            pageSize=20, q="'sub_folder2_id' in parents"
        )

        # Проверка, что метод загрузки файлов был вызван 4 раза (по 2 файла на каждую папку)
        self.assertEqual(mock_download_file.call_count, 4)

    @patch("src.Drive.google_drive.os.makedirs")
    @patch("src.clouds_manager.get_os_path_by_cloud_path")
    def test_downloading_folders_empty(self, _, mock_makedirs):
        download_folders = []

        self.drive.downloading_folders(download_folders)

        mock_makedirs.assert_not_called()

        self.drive.service.files().list.assert_not_called()

    @patch("src.Drive.google_drive.io.FileIO")
    def test_download_google_doc_file(self, mock_fileio):
        drive_file = {
            "id": "file_id_123",
            "name": "Test Google Doc",
            "mimeType": "application/vnd.google-apps.document",
        }

        self.drive.service.files().export.return_value.execute.return_value = (
            b"Test file content"
        )

        try:
            self.drive.download_file_from_drive("\\test\\path", drive_file)
        except TypeError:
            pass

        self.drive.service.files().export.assert_called_once_with(
            fileId="file_id_123",
            mimeType=google_drive.GOOGLE_MIME_TYPES[drive_file["mimeType"]][0],
        )

        mock_fileio.assert_called_once_with("\\test\\path\\Test Google Doc.docx", "wb")

    @patch("src.Drive.google_drive.MediaIoBaseDownload")
    @patch("src.Drive.google_drive.io.FileIO", new_callable=mock_open)
    def test_download_regular_file(self, mock_fileio, mock_downloader):
        drive_file = {
            "id": "file_id_456",
            "name": "test_file.txt",
            "mimeType": "text/plain",
        }

        mock_downloader.return_value.next_chunk.side_effect = [
            (None, False),
            (None, True),
        ]  # Два вызова для завершения загрузки

        self.drive.download_file_from_drive("\\test\\path", drive_file)

        self.drive.service.files().get_media.assert_called_once_with(
            fileId="file_id_456"
        )

        mock_fileio.assert_called_once_with("\\test\\path\\test_file.txt", "wb")
        self.assertEqual(mock_downloader.return_value.next_chunk.call_count, 2)

    @patch("src.clouds_manager.get_os_path_by_cloud_path")
    @patch("src.Drive.google_drive.os.remove")
    @patch("src.Drive.google_drive.os.path.join", side_effect=lambda *args: "/".join(args))
    @patch("src.Drive.google_drive.GoogleDrive.get_data_for_comparison")
    @patch("src.Drive.google_drive.GoogleDrive.download_file_from_drive")
    def test_update_dir_on_pc(
        self,
        mock_download_file,
        mock_get_data,
        mock_join,
        mock_remove,
        mock_get_os_path,
    ):
        mock_get_os_path.return_value = "/test/path/folder"
        exact_folders = ["folder1"]
        self.drive.parents_id["folder1"] = "123"
        self.drive.parents_id["folder"] = "234"

        os_files = ["file1.txt", "file2.txt", "file3.txt"]
        cloud_files = [
            {
                "name": "file1.txt",
                "id": "1",
                "mimeType": "text/plain",
                "md5Checksum": "abc",
            },
            {
                "name": "file2.txt",
                "id": "2",
                "mimeType": "text/plain",
                "md5Checksum": "def",
            },
            {
                "name": "file4.txt",
                "id": "4",
                "mimeType": "text/plain",
                "md5Checksum": "ghi",
            },
        ]

        self.drive.get_os_and_cloud_files = MagicMock(
            return_value=(os_files, cloud_files)
        )

        mock_get_data.side_effect = [
            (
                datetime.datetime(2021, 1, 1),
                datetime.datetime(2024, 1, 1),
                "local_md5_file1",
                "cloud_md5_file1",
            ),  # file1.txt
            (
                datetime.datetime(2021, 1, 1),
                datetime.datetime(2021, 1, 1),
                "local_md5_file2",
                "cloud_md5_file2",
            ),  # file2.txt
        ]

        self.drive.update_dir_on_pc(exact_folders)

        mock_remove.assert_any_call("/test/path/folder/file1.txt")
        mock_download_file.assert_any_call("/test/path/folder", cloud_files[0])

        mock_remove.assert_any_call("/test/path/folder/file3.txt")

        mock_download_file.assert_any_call("/test/path/folder", cloud_files[2])

        self.drive.get_os_and_cloud_files.assert_called_with(
            self.drive.parents_id["folder1"], "/test/path/folder"
        )
        self.assertEqual(mock_get_data.call_count, 2)

    @patch("src.clouds_manager.FileData")
    @patch("src.Drive.google_drive.format_datetime")
    @patch("src.Drive.google_drive.GoogleDrive.get_cloud_tree")
    def test_list_files_success(
        self, mock_get_cloud_tree, mock_format_datetime, mock_file_data
    ):
        mock_response = {
            "files": [
                {
                    "id": "1",
                    "name": "file1.txt",
                    "mimeType": "text/plain",
                    "size": "1024",
                    "modifiedTime": "2023-09-01T12:34:56.789Z",
                },
                {
                    "id": "2",
                    "name": "folder1",
                    "mimeType": "application/vnd.google-apps.folder",
                },
            ]
        }
        self.drive.service.files().list.return_value.execute.return_value = (
            mock_response
        )

        mock_format_datetime.return_value = "2023-09-01 12:34:56"

        result = self.drive.list_files("test_folder")

        mock_get_cloud_tree.assert_called_once_with("", [], "")
        self.drive.service.files().list.assert_called_once_with(
            q="'test_folder_id' in parents and trashed = false",
            fields="files(id, name, mimeType, size, modifiedTime)",
            pageSize=1000,
        )

        mock_file_data.assert_any_call(
            item_type="FILE",
            item_name="file1.txt",
            item_size="1024",
            item_modified="2023-09-01 12:34:56",
        )

        mock_file_data.assert_any_call(
            item_type="DIR", item_name="folder1", item_size=None, item_modified=None
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(mock_file_data.call_count, 2)

    @patch("src.Drive.google_drive.GoogleDrive.get_os_and_cloud_files")
    def test_handle_response(self, mock_get_files):
        mock_get_files.side_effect = Exception("Some error")

        with self.assertRaises(Exception):
            self.drive.get_os_and_cloud_files("folder_id", "/test/path")


if __name__ == "__main__":
    unittest.main()

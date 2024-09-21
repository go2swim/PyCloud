import unittest
import datetime
import json

from src.Dropbox.dropbox import DropBox, DROPBOX_CONTENT_URL, DROPBOX_API_URL
from unittest.mock import patch, MagicMock, mock_open

import sys
import os

from src.clouds_manager import FileData

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class TestDropboxMethods(unittest.TestCase):

    def setUp(self):
        self.mock_headers_manager = patch(
            "src.Dropbox.dropbox.DropboxHeadersManager"
        ).start()

        self.mock_headers_manager.return_value.headers = {
            "Authorization": "Bearer FAKE_TOKEN",
            "Content-Type": "application/json",
        }

        self.mock_headers_manager.return_value.token_manager = MagicMock()
        self.mock_headers_manager.return_value.token = "FAKE_TOKEN"

        self.dropbox = DropBox("test_dir", "/fake/path")

    @patch("src.Dropbox.dropbox.requests.post")
    @patch("src.Dropbox.dropbox.DropboxHeadersManager")
    def test_handle_response_success(self, mock_headers_manager, mock_post):
        """Test handle_response for a successful response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        result = self.dropbox.handle_response(mock_response)
        self.assertEqual(result, {"success": True})

    @patch("src.Dropbox.dropbox.requests.request")
    @patch("src.Dropbox.dropbox.requests.post")
    @patch("src.Dropbox.dropbox.DropboxHeadersManager")
    def test_handle_response_401_refresh(
        self, mock_headers_manager, mock_post, requests_mock
    ):
        """Test handle_response retries on a 401 Unauthorized response."""

        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401
        mock_response_401.json.return_value = {"error_summary": "Unauthorized"}

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"success": True}

        mock_headers_manager.return_value.token_manager.refresh_token.return_value = (
            None
        )
        mock_post.return_value = mock_response_200

        requests_mock.return_value = mock_response_200

        result = self.dropbox.handle_response(mock_response_401)
        self.assertEqual(result, {"success": True})
        requests_mock.assert_called_once()

    @patch("src.Dropbox.dropbox.requests.post")
    def test_handle_response_failure(self, mock_post):
        """Test handle_response raises exception on failure."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error_summary": "Internal Server Error"}

        with self.assertRaises(Exception) as context:
            self.dropbox.handle_response(mock_response)

        self.assertIn("Ошибка 500", str(context.exception))

    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    @patch("src.Dropbox.dropbox.requests.post")
    @patch("src.Dropbox.dropbox.DropboxHeadersManager")
    def test_upload_file_success(self, mock_headers_manager, mock_post, mock_file):
        """Test upload_file for a successful file upload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "testfile"}

        mock_post.return_value = mock_response

        self.dropbox.upload_file(
            "testfile.txt", "/path_in_dropbox/testfile.txt", replace=True
        )

        mock_post.assert_called_once_with(
            f"{DROPBOX_CONTENT_URL}/files/upload",
            headers={
                "Authorization": "Bearer FAKE_TOKEN",
                "Content-Type": "application/octet-stream",
                "Dropbox-API-Arg": '{"path": "/path_in_dropbox/testfile.txt", "mode": "overwrite", "autorename": true, "mute": false}',
            },
            data=mock_file(),
        )
        self.assertTrue(mock_file.called)

    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    @patch("src.Dropbox.dropbox.requests.post")
    @patch("src.Dropbox.dropbox.DropboxHeadersManager")
    def test_upload_file_failure(self, mock_headers_manager, mock_post, mock_file):
        """Test upload_file failure scenario."""

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        with self.assertRaises(Exception):
            self.dropbox.upload_file("testfile.txt", "/path_in_dropbox/testfile.txt")

    @patch("src.Dropbox.dropbox.requests.post")
    @patch("src.Dropbox.dropbox.DropboxHeadersManager")
    def test_delete_success(self, mock_headers_manager, mock_post):
        """Test delete for successful resource deletion."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"metadata": {"name": "testfile"}}

        mock_post.return_value = mock_response

        self.dropbox.delete("/path_in_dropbox/testfile.txt")

        mock_post.assert_called_once_with(
            f"{DROPBOX_API_URL}/files/delete_v2",
            headers={
                "Authorization": "Bearer FAKE_TOKEN",
                "Content-Type": "application/json",
            },
            data=json.dumps({"path": "/path_in_dropbox/testfile.txt"}),
        )

    @patch("src.Dropbox.dropbox.requests.post")
    def test_delete_failure(self, mock_post):
        """Test delete failure scenario."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_post.return_value = mock_response

        with self.assertRaises(Exception):
            self.dropbox.delete("/path_in_dropbox/nonexistent.txt")

    @patch("src.Dropbox.dropbox.requests.post")
    @patch("src.Dropbox.dropbox.DropboxHeadersManager")
    def test_create_folder_success(self, mock_headers_manager, mock_post):
        """Test create_folder for a successful folder creation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"metadata": {"name": "testfolder"}}

        mock_post.return_value = mock_response

        self.dropbox.create_folder("/path_in_dropbox/testfolder")

        mock_post.assert_called_once_with(
            f"{DROPBOX_API_URL}/files/create_folder_v2",
            headers={
                "Authorization": "Bearer FAKE_TOKEN",
                "Content-Type": "application/json",
            },
            data=json.dumps(
                {"path": "/path_in_dropbox/testfolder", "autorename": False}
            ),
        )

    @patch("src.Dropbox.dropbox.requests.post")
    def test_create_folder_failure(self, mock_post):
        """Test create_folder failure scenario."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        with self.assertRaises(Exception):
            self.dropbox.create_folder("/path_in_dropbox/failure_test")

    def tearDown(self):
        patch.stopall()

    @patch("src.Dropbox.dropbox.requests.post")
    def test_list_folder_success(self, mock_post):
        """Test list_folder for successful response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "entries": [
                {"name": "testfile.txt", ".tag": "file"},
                {"name": "testfolder", ".tag": "folder"},
            ]
        }
        mock_post.return_value = mock_response

        result = self.dropbox.list_folder("/fake/path")
        self.assertEqual(len(result["entries"]), 2)
        self.assertEqual(result["entries"][0]["name"], "testfile.txt")

        mock_post.assert_called_once_with(
            f"{DROPBOX_API_URL}/files/list_folder",
            headers={
                "Authorization": "Bearer FAKE_TOKEN",
                "Content-Type": "application/json",
            },
            data=json.dumps({"path": "/fake/path"}),
        )

    @patch("src.Dropbox.dropbox.requests.post")
    def test_check_root_folder_exists(self, mock_post):
        """Test check_root_folder when folder exists."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"entries": [{"name": "SYNC_FOLDERS"}]}

        mock_post.return_value = mock_response

        result = self.dropbox.check_root_folder()
        self.assertTrue(result)

    @patch("src.Dropbox.dropbox.DropBox.create_folder")
    @patch("src.Dropbox.dropbox.requests.post")
    def test_check_upload_success(self, mock_post, mock_create_folder):
        """Test check_upload for successful upload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"entries": []}

        mock_post.return_value = mock_response

        self.dropbox.check_upload()
        mock_create_folder.assert_called()

    @patch("src.Dropbox.dropbox.requests.post")
    def test_get_cloud_tree_success(self, mock_post):
        """Test get_cloud_tree for successfully retrieving folder structure."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            {
                "entries": [
                    {"name": "testfile.txt", ".tag": "file"},
                    {"name": "testfolder", ".tag": "folder"},
                ]
            },
            {},
        ]
        mock_post.return_value = mock_response

        tree_list = []
        self.dropbox.get_cloud_tree("/fake/path", tree_list, "")
        self.assertEqual(len(tree_list), 1)
        self.assertIn(f"/fake/path{os.path.sep}testfolder", tree_list)

    @patch("os.listdir", return_value=["file1.txt", "file2.txt"])
    @patch("src.Dropbox.dropbox.requests.post")
    def test_upload_dir_on_cloud_success(self, mock_post, mock_walk):
        """Test upload_dir_on_cloud for successful directory upload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "file"}

        mock_post.return_value = mock_response

        self.dropbox.upload_dir_on_cloud(["/fake/path"])

        self.assertEqual(mock_post.call_count, 1)

    @patch("os.path.getmtime", return_value=1609459200)
    @patch("builtins.open", new_callable=mock_open, read_data=b"test content")
    @patch("hashlib.md5")
    def test_get_data_for_comparison(self, mock_md5, mock_open, mock_getmtime):
        """Test get_data_for_comparison for proper comparison of local and cloud files."""
        mock_md5.return_value.hexdigest.return_value = "abc123"

        os_path_file = "/local/test_folder/file1.txt"
        cloud_file = {
            "name": "file1.txt",
            "server_modified": "2021-01-01T12:00:00+00:00",
            "content_hash": "abc123",
        }

        os_modified_time, cloud_modified_time, os_file_md5, cloud_file_md5 = (
            self.dropbox.get_data_for_comparison(os_path_file, cloud_file)
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

    @patch("src.Dropbox.dropbox.DropBox.list_folder")
    @patch("os.listdir")
    @patch("os.path.isfile")
    def test_get_os_and_clouds_files(self, isfile_mock, listdir_mock, list_folder_mock):
        """Test getting files from OS and cloud."""
        listdir_mock.return_value = ["file1.txt", "file2.txt", "file3.txt"]
        isfile_mock.side_effect = lambda path: path.endswith(".txt")

        list_folder_mock.return_value = {
            "entries": [
                {".tag": "file", "name": "file2.txt"},
                {".tag": "file", "name": "file4.txt"},
            ]
        }

        os_files, cloud_files = self.dropbox.get_os_and_clouds_files(
            "test_folder", "/fake/path"
        )

        self.assertEqual(os_files, ["file1.txt", "file2.txt", "file3.txt"])
        self.assertEqual([f["name"] for f in cloud_files], ["file2.txt", "file4.txt"])

    @patch("src.Dropbox.dropbox.DropBox.upload_file")
    @patch("src.Dropbox.dropbox.DropBox.delete")
    @patch("src.Dropbox.dropbox.DropBox.get_os_and_clouds_files")
    @patch("src.Dropbox.dropbox.DropBox.get_data_for_comparison")
    def test_update_dir_on_cloud(
        self,
        get_data_for_comparison_mock,
        get_os_and_clouds_files_mock,
        delete_mock,
        upload_file_mock,
    ):
        """Test updating directory on cloud."""
        get_os_and_clouds_files_mock.return_value = (
            ["file1.txt", "file2.txt"],
            [
                {"name": "file2.txt", "path_display": "/dropbox/path/file2.txt"},
                {"name": "file3.txt", "path_display": "/dropbox/path/file3.txt"},
            ],
        )

        get_data_for_comparison_mock.side_effect = [
            (10, 9, "fake_md5_os", "fake_md5_cloud"),
        ]

        self.dropbox.update_dir_on_cloud(["test_folder"])

        upload_file_mock.assert_called_with(
            f"{os.path.sep}test_folder{os.path.sep}file1.txt",
            "/SYNC_FOLDERS/test_folder/file1.txt",
        )
        delete_mock.assert_called_with("/dropbox/path/file3.txt")

    @patch("src.clouds_manager.get_os_path_by_cloud_path", return_value="test_folder")
    @patch("src.Dropbox.dropbox.DropBox.download")
    @patch("src.Dropbox.dropbox.DropBox.get_os_and_clouds_files")
    @patch("src.Dropbox.dropbox.DropBox.get_data_for_comparison")
    @patch("os.remove")
    def test_update_dir_on_pc(
        self,
        remove_mock,
        get_data_for_comparison_mock,
        get_os_and_clouds_files_mock,
        download_mock,
        _,
    ):
        """Test updating directory on PC."""
        get_os_and_clouds_files_mock.return_value = (
            ["file1.txt", "file2.txt"],
            [
                {"name": "file2.txt", "path_display": "/dropbox/path/file2.txt"},
                {"name": "file3.txt", "path_display": "/dropbox/path/file3.txt"},
            ],
        )

        get_data_for_comparison_mock.side_effect = [
            (8, 9, "fake_md5_os", "fake_md5_cloud"),
        ]

        self.dropbox.update_dir_on_pc(["test_folder"])

        download_mock.assert_called_with(
            "test_folder", "/dropbox/path/file3.txt", is_folder=False
        )
        remove_mock.assert_called_once_with(f"test_folder{os.path.sep}file1.txt")

    @patch("src.Dropbox.dropbox.DropBox.delete")
    def test_remove_old_dir_on_cloud(self, delete_mock):
        """Test removing old directories from cloud."""
        remove_folders = ["folder1", "folder2"]
        self.dropbox.remove_old_dir_on_cloud(remove_folders)

        from src.clouds_manager import ROOT_FOLDER

        delete_mock.assert_any_call(f"/{ROOT_FOLDER}/folder1")
        delete_mock.assert_any_call(f"/{ROOT_FOLDER}/folder2")
        self.assertEqual(delete_mock.call_count, 2)

    @patch("src.Dropbox.dropbox.DropBox.handle_response")
    @patch("src.Dropbox.dropbox.requests.post")
    def test_list_files(self, post_mock, handle_response_mock):
        """Test listing files and directories."""

        post_mock.return_value = MagicMock()
        handle_response_mock.return_value = {
            "entries": [
                {
                    ".tag": "file",
                    "name": "file1.txt",
                    "size": 1000,
                    "server_modified": "2022-01-01T12:00:00Z",
                },
                {".tag": "folder", "name": "folder1"},
            ]
        }

        result = self.dropbox.list_files("/test_path")

        expected_result = [
            FileData(
                item_type="FILE",
                item_name="file1.txt",
                item_size=1000,
                item_modified=datetime.datetime.fromisoformat("2022-01-01T12:00:00Z"),
            ),
            FileData(
                item_type="DIR", item_name="folder1", item_size=None, item_modified=None
            ),
        ]
        self.assertEqual(result, expected_result)

        post_mock.assert_called_once_with(
            f"{DROPBOX_API_URL}/files/list_folder",
            headers=self.dropbox.headers.headers,
            data=json.dumps({"path": "/test_path", "limit": 1000}),
        )

    @patch("src.Dropbox.dropbox.os.path.exists")
    @patch("src.Dropbox.dropbox.DropBox.download")
    @patch("src.clouds_manager.get_os_path_by_cloud_path")
    def test_downloading_folders(self, get_os_path_mock, download_mock, exists_mock):
        """Test downloading folders from Dropbox."""

        get_os_path_mock.side_effect = lambda folder: f"/local/path/{folder}"

        exists_mock.side_effect = [
            False,
            True,
        ]

        download_folders = ["folder1", "folder2/subfolder"]
        self.dropbox.downloading_folders(download_folders)

        download_mock.assert_called_once_with(
            "", "/SYNC_FOLDERS/folder1", is_folder=True
        )

    @patch("src.Dropbox.dropbox.DropBox.download_file")
    @patch("src.Dropbox.dropbox.DropBox.list_folder")
    @patch("os.makedirs")
    def test_download_folder(self, makedirs_mock, list_folder_mock, download_file_mock):
        """Test downloading a folder with multiple files from Dropbox."""
        list_folder_mock.return_value = {
            "entries": [
                {
                    ".tag": "file",
                    "name": "file1.txt",
                    "path_display": "/dropbox/file1.txt",
                },
                {
                    ".tag": "file",
                    "name": "file2.txt",
                    "path_display": "/dropbox/file2.txt",
                },
            ]
        }

        self.dropbox.download("/local/path", "/dropbox/folder", is_folder=True)

        makedirs_mock.assert_called_once_with(
            f"/local/path{os.path.sep}folder", exist_ok=True
        )

        download_file_mock.assert_any_call(
            f"/local/path{os.path.sep}folder", "/dropbox/file1.txt"
        )
        download_file_mock.assert_any_call(
            f"/local/path{os.path.sep}folder", "/dropbox/file2.txt"
        )

    @patch("src.Dropbox.dropbox.DropBox.download_file")
    def test_download_file(self, download_file_mock):
        """Test downloading a single file."""

        self.dropbox.download("/local/path", "/dropbox/file.txt", is_folder=False)

        download_file_mock.assert_called_once_with("/local/path", "/dropbox/file.txt")

    @patch("src.Dropbox.dropbox.os.path.join")
    @patch("src.Dropbox.dropbox.os.path.basename")
    @patch("src.Dropbox.dropbox.open", new_callable=mock_open)
    @patch("src.Dropbox.dropbox.requests.post")
    @patch("src.Dropbox.dropbox.DropBox.handle_response")
    def test_download_file(
        self, handle_response_mock, post_mock, open_mock, basename_mock, join_mock
    ):
        """Test downloading a single file from Dropbox."""

        downloaded_path = "/local/path"
        save_path = "/dropbox/file.txt"
        file_name = "file.txt"
        file_content = b"file content"

        basename_mock.return_value = file_name
        join_mock.return_value = f"{downloaded_path}/{file_name}"

        post_mock.return_value = MagicMock(status_code=200)
        post_mock.return_value.iter_content = MagicMock(return_value=[file_content])

        self.dropbox.download_file(downloaded_path, save_path)

        post_mock.assert_called_once_with(
            f"{DROPBOX_CONTENT_URL}/files/download",
            headers={
                "Authorization": f"Bearer {self.dropbox.headers.token}",
                "Dropbox-API-Arg": json.dumps({"path": f"{save_path}"}),
            },
            stream=True,
        )

        open_mock.assert_called_once_with(f"{downloaded_path}/{file_name}", "wb")

        open_mock().write.assert_called_once_with(file_content)

        basename_mock.assert_called_with(save_path)

    @patch("src.Dropbox.dropbox.requests.post")
    @patch("src.Dropbox.dropbox.DropBox.handle_response")
    def test_download_file_failed(self, handle_response_mock, post_mock):
        """Test handling failed file download."""

        downloaded_path = "/local/path"
        save_path = "/dropbox/file.txt"

        post_mock.return_value = MagicMock(status_code=404)

        self.dropbox.download_file(downloaded_path, save_path)

        handle_response_mock.assert_called_once_with(post_mock.return_value)


if __name__ == "__main__":
    unittest.main()

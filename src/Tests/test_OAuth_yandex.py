import unittest
from unittest import mock
from unittest.mock import patch, mock_open, MagicMock

from src.Yandex.OAuth_yandex import YandexTokenManager, YandexHeadersManager


class TestYandexTokenManager(unittest.TestCase):

    @patch("builtins.open", new_callable=mock_open, read_data="fake_token")
    def test_get_access_token_from_file(self, mock_file):
        """Test successful token retrieval from file."""
        manager = YandexTokenManager()
        token = manager.get_access_token()

        # Проверка, что токен был правильно прочитан из файла
        mock_file.assert_called_once_with(manager.token_file, 'r')
        self.assertEqual(token, "fake_token")

    @patch("builtins.open", mock_open(read_data=""))
    @patch.object(YandexTokenManager, 'refresh_token', return_value="new_fake_token")
    def test_get_access_token_refresh_token(self, mock_refresh_token):
        """Test token retrieval when file is empty, should call refresh_token."""
        manager = YandexTokenManager()
        token = manager.get_access_token()

        mock_refresh_token.assert_called_once()
        self.assertEqual(token, "new_fake_token")

    @patch("builtins.open", side_effect=FileNotFoundError)
    @patch.object(YandexTokenManager, 'refresh_token', return_value="new_fake_token")
    def test_get_access_token_file_not_found(self, mock_refresh_token, mock_file):
        """Test token retrieval when file is not found, should call refresh_token."""
        manager = YandexTokenManager()
        token = manager.get_access_token()

        # Проверка, что была вызвана функция обновления токена при отсутствии файла
        mock_refresh_token.assert_called_once()
        self.assertEqual(token, "new_fake_token")

    @patch("builtins.open", mock_open())
    @patch.object(YandexTokenManager, 'authentication', return_value="new_access_token")
    def test_refresh_token(self, mock_authentication):
        """Test refreshing token by calling the authentication method."""
        manager = YandexTokenManager()
        token = manager.refresh_token()

        # Проверка, что токен был записан в файл и был вызван метод аутентификации
        mock_authentication.assert_called_once()
        self.assertEqual(token, "new_access_token")

    @patch('src.Yandex.OAuth_yandex.requests.post')
    @patch('src.Yandex.OAuth_yandex.webbrowser.open')
    @patch('src.Yandex.OAuth_yandex.YandexTokenManager.start_server')
    @patch('src.Yandex.OAuth_yandex.YandexTokenManager._handle_callback')
    def test_authentication(self, mock_handle_callback, mock_start_server, mock_webbrowser, mock_post):
        """Test the authentication process including code verifier/challenge generation and token exchange."""
        manager = YandexTokenManager()

        manager.server_shutdown = True
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "new_access_token"}
        mock_post.return_value = mock_response

        manager.auth_code = "auth_code"

        token = manager.authentication()

        mock_webbrowser.assert_called_once()
        mock_start_server.assert_called_once()
        mock_post.assert_called_once_with(
            "https://oauth.yandex.ru/token",
            data={
                "code": "auth_code",
                "grant_type": "authorization_code",
                "client_id": manager.client_id,
                "redirect_uri": manager.redirect_uri,
                "code_verifier": mock.ANY
            }
        )

        self.assertEqual(token, "new_access_token")

    @patch('http.server.HTTPServer')
    @patch('threading.Thread')
    def test_start_server(self, mock_thread, mock_http_server):
        """Test starting the local server for OAuth callback handling."""
        manager = YandexTokenManager()

        # Проверка, что сервер запускается с нужными параметрами и что был создан поток
        manager.start_server()
        mock_thread.assert_called_once()

    def test_handle_callback(self):
        """Test handling the authorization callback."""
        manager = YandexTokenManager()
        manager._handle_callback("auth_code")

        self.assertEqual(manager.auth_code, "auth_code")
        self.assertTrue(manager.server_shutdown)

    @patch.object(YandexTokenManager, 'get_access_token', return_value="fake_access_token")
    def test_token_property(self, mock_get_access_token):
        """Test that the token property retrieves the access token."""
        headers_manager = YandexHeadersManager()

        # Проверка, что свойство token возвращает ожидаемый токен
        token = headers_manager.token
        mock_get_access_token.assert_called_once()
        self.assertEqual(token, "fake_access_token")

if __name__ == "__main__":
    unittest.main()
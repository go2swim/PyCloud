import os
import base64
import hashlib
import requests
import urllib
import webbrowser
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class YandexHeadersManager:
    def __init__(self):
        self.token_manager = YandexTokenManager()

    @property
    def token(self):
        return self.token_manager.get_access_token()

    def refresh_token(self):
        self.token_manager.refresh_token()


class YandexTokenManager:
    def __init__(self):
        current_dir = os.path.basename(os.getcwd())
        if current_dir == "PyCloud":
            token_file = os.path.join("src", "Yandex", "access_token_for_yandex")
        elif current_dir == "src":
            token_file = os.path.join("Yandex", "access_token_for_yandex")
        elif current_dir == "Yandex":
            token_file = "access_token_for_yandex"
        elif current_dir == "Tests":
            token_file = os.path.join("..", "Yandex", "access_token_for_yandex")
        else:
            raise FileNotFoundError("Is start directory not found")

        self.token_file = token_file
        self.client_id = "4b0aae0b436149aea3e8de9191408f82"
        self.redirect_uri = "http://localhost:8080/callback"
        self.auth_code = None
        self.server = None
        self.server_shutdown = False  # Флаг для остановки сервера

    def get_access_token(self):
        """
        Получить access token из файла или обновить его через refresh token.
        """
        try:
            with open(self.token_file, "r") as file:
                token = file.read().strip()
                if token:
                    return token
                else:
                    return self.refresh_token()
        except FileNotFoundError:
            return self.refresh_token()

    def refresh_token(self):
        """
        Процедура получения токена (через авторизацию пользователя).
        """
        token = self.authentication()
        with open(self.token_file, "w") as file:
            file.write(token)
        return token

    def authentication(self):
        """
        Основной процесс аутентификации: получение кода и обмен на токен.
        """
        # 1. Генерация code_verifier и code_challenge для PKCE
        code_verifier = (
            base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("utf-8")
        )
        code_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode("utf-8")).digest()
            )
            .rstrip(b"=")
            .decode("utf-8")
        )

        # 2. Ссылка для авторизации
        auth_url = (
            f"https://oauth.yandex.ru/authorize"
            f"?client_id={self.client_id}"
            f"&response_type=code"
            f"&redirect_uri={urllib.parse.quote(self.redirect_uri)}"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
        )

        # 3. Запуск локального сервера для получения кода авторизации
        self.start_server()

        # 4. Открытие браузера с авторизационной ссылкой
        webbrowser.open(auth_url)
        print("Ожидание авторизации...")

        # 5. Ждем завершения работы сервера
        while not self.server_shutdown:
            pass

        # 6. Обмен кода авторизации на токен
        token_url = "https://oauth.yandex.ru/token"
        data = {
            "code": self.auth_code,
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier,  # Передаем изначальный code_verifier
        }

        response = requests.post(token_url, data=data)
        tokens = response.json()

        ACCESS_TOKEN = tokens.get("access_token")
        print("Access Token:", ACCESS_TOKEN)
        return ACCESS_TOKEN

    def start_server(self):
        """
        Запуск локального сервера для перехвата кода авторизации.
        """
        self.server = HTTPServer(("localhost", 8080), self.CallbackHandler)
        self.server.callback = self._handle_callback
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.start()

    def _handle_callback(self, code):
        """
        Обработка кода авторизации, полученного с сервера.
        """
        self.auth_code = code
        print(f"Код авторизации получен: {code}")
        self.server_shutdown = True  # Устанавливаем флаг для завершения работы сервера

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            """
            Обрабатываем GET-запрос для получения кода авторизации.
            """
            query_components = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query
            )
            code = query_components.get("code", [None])[0]

            if code:
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Authorization complete! You can close this window.</h1></body></html>"
                )
                self.server.callback(code)
            else:
                self.send_response(400)
                self.end_headers()


if __name__ == "__main__":
    yandex_manager = YandexHeadersManager()

    # Получаем заголовки с токеном для запроса
    headers = yandex_manager.token
    print(headers)

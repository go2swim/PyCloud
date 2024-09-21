import threading
import urllib
import webbrowser
import base64
import hashlib
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests


class DropboxHeadersManager:
    def __init__(self):
        self.token_manager = DropboxTokenManager()

    @property
    def token(self):
        return self.token_manager.get_access_token()

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }


class DropboxTokenManager:
    def __init__(self):
        current_dir = os.getcwd()
        if os.path.basename(current_dir) == "PyCloud":
            token_file = os.path.join("src", "Dropbox", "access_token_for_dropbox")
        elif os.path.basename(current_dir) == "src":
            token_file = os.path.join("Dropbox", "access_token_for_dropbox")
        elif os.path.basename(current_dir) == "Dropbox":
            token_file = "access_token_for_dropbox"
        elif os.path.basename(current_dir) == "Tests":
            token_file = os.path.join("..", "Dropbox", "access_token_for_dropbox")
        else:
            raise FileNotFoundError("Is start directory not found")

        self.token_file = token_file
        self.client_id = "vfbn1vqes5gz2pl"
        self.redirect_uri = "http://localhost:8080/callback"
        self.auth_code = None
        self.server = None
        self.server_shutdown = False  # Флаг для остановки сервера

    def get_access_token(self):
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
        token = self.authentication()
        with open(self.token_file, "w") as file:
            file.write(token)
        return token

    def authentication(self):
        # Генерация code_verifier и code_challenge
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

        auth_url = (
            f"https://www.dropbox.com/oauth2/authorize"
            f"?client_id={self.client_id}"
            f"&response_type=code"
            f"&redirect_uri={urllib.parse.quote(self.redirect_uri)}"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
        )

        # Запуск локального сервера для перехвата кода
        self.start_server()

        # Открытие браузера с авторизационным URL
        webbrowser.open(auth_url)
        print("Ожидание авторизации...")

        while not self.server_shutdown:
            pass

        token_url = "https://api.dropboxapi.com/oauth2/token"
        data = {
            "code": self.auth_code,
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier,  # Передаём оригинальный code_verifier
        }

        response = requests.post(token_url, data=data)
        tokens = response.json()

        ACCESS_TOKEN = tokens.get("access_token")
        print("Access Token:", ACCESS_TOKEN)
        return ACCESS_TOKEN

    def start_server(self):
        """Запускает локальный сервер для перехвата кода авторизации."""
        self.server = HTTPServer(("localhost", 8080), self.CallbackHandler)
        self.server.callback = self._handle_callback
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.start()

    def _handle_callback(self, code):
        """Обработка полученного кода авторизации."""
        self.auth_code = code
        print(f"Код авторизации получен: {code}")
        self.server_shutdown = True  # Устанавливаем флаг для завершения работы сервера

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            """Обрабатываем GET-запрос для получения кода авторизации."""
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

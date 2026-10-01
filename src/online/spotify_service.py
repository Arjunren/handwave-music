from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Signal

SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_URL = "https://api.spotify.com/v1"


@dataclass(frozen=True, slots=True)
class SpotifyResult:
    name: str
    subtitle: str
    url: str
    kind: str


class _CallbackServer(HTTPServer):
    callback: dict[str, str] | None = None


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        values = {key: entries[0] for key, entries in parse_qs(parsed.query).items() if entries}
        self.server.callback = values  # type: ignore[attr-defined]
        approved = "code" in values and "error" not in values
        message = (
            "Spotify is connected. You can close this browser tab."
            if approved
            else "Spotify connection was not approved."
        )
        body = f"<html><body><h2>{message}</h2></body></html>".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


class SpotifyService(QObject):
    """Session-only Spotify catalog search using Authorization Code with PKCE."""

    authorization_requested = Signal(str)
    connected = Signal()
    connection_failed = Signal(str)
    results_ready = Signal(int, object)
    search_failed = Signal(int, str)

    def __init__(self) -> None:
        super().__init__()
        self._access_token = ""
        self._connecting = False
        self._lock = threading.Lock()

    @property
    def connected_to_spotify(self) -> bool:
        return bool(self._access_token)

    def connect(self, client_id: str) -> None:
        client_id = client_id.strip()
        if len(client_id) < 12 or len(client_id) > 128:
            self.connection_failed.emit("Enter the Client ID from your Spotify developer app.")
            return
        with self._lock:
            if self._connecting:
                return
            self._connecting = True
        threading.Thread(target=self._authorize, args=(client_id,), daemon=True, name="spotify-auth").start()

    def search(self, query: str, kind: str, request_id: int) -> None:
        query = query.strip()
        if not self._access_token:
            self.search_failed.emit(request_id, "Connect Spotify before searching.")
            return
        if not query:
            self.results_ready.emit(request_id, [])
            return
        threading.Thread(
            target=self._search, args=(query, kind, request_id), daemon=True, name="spotify-search"
        ).start()

    def _authorize(self, client_id: str) -> None:
        server: _CallbackServer | None = None
        try:
            verifier = secrets.token_urlsafe(64)
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
            )
            state = secrets.token_urlsafe(24)
            server = _CallbackServer(("127.0.0.1", 0), _CallbackHandler)
            server.timeout = 180
            redirect_uri = f"http://127.0.0.1:{server.server_port}/callback"
            query = urlencode(
                {
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": redirect_uri,
                    "code_challenge_method": "S256",
                    "code_challenge": challenge,
                    "state": state,
                }
            )
            authorization_url = f"{SPOTIFY_AUTHORIZE_URL}?{query}"
            self.authorization_requested.emit(authorization_url)
            server.handle_request()
            callback = server.callback or {}
            if callback.get("state") != state:
                raise RuntimeError("Spotify authorization expired or returned an invalid state.")
            if callback.get("error"):
                raise RuntimeError("Spotify authorization was cancelled.")
            code = callback.get("code")
            if not code:
                raise RuntimeError("Spotify did not return an authorization code.")
            token = self._request_json(
                SPOTIFY_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": verifier,
                },
            )
            access_token = token.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise RuntimeError("Spotify did not return an access token.")
            self._access_token = access_token
            self.connected.emit()
        except Exception as exc:
            self.connection_failed.emit(str(exc)[:300])
        finally:
            if server is not None:
                server.server_close()
            with self._lock:
                self._connecting = False

    def _search(self, query: str, kind: str, request_id: int) -> None:
        try:
            response = self._request_json(
                f"{SPOTIFY_API_URL}/search?{urlencode({'q': query, 'type': kind, 'limit': 20})}",
                access_token=self._access_token,
            )
            container = response.get(f"{kind}s", {})
            raw_items = container.get("items", []) if isinstance(container, dict) else []
            results = [self._to_result(item, kind) for item in raw_items if isinstance(item, dict)]
            self.results_ready.emit(request_id, results)
        except Exception as exc:
            self.search_failed.emit(request_id, str(exc)[:300])

    @staticmethod
    def _to_result(item: dict[str, Any], kind: str) -> SpotifyResult:
        name = str(item.get("name") or "Untitled")[:180]
        artists = item.get("artists")
        if isinstance(artists, list):
            subtitle = ", ".join(
                str(artist.get("name", "")) for artist in artists if isinstance(artist, dict)
            )
        elif kind == "artist":
            subtitle = "Artist"
        elif kind == "playlist":
            owner = item.get("owner")
            subtitle = str(owner.get("display_name") or "Playlist") if isinstance(owner, dict) else "Playlist"
        else:
            subtitle = (
                str(item.get("album", {}).get("name", ""))
                if isinstance(item.get("album"), dict)
                else kind.title()
            )
        external = item.get("external_urls")
        raw_url = str(external.get("spotify", "")) if isinstance(external, dict) else ""
        parsed = urlparse(raw_url)
        url = raw_url if parsed.scheme == "https" and parsed.hostname == "open.spotify.com" else ""
        return SpotifyResult(name, subtitle or kind.title(), url, kind)

    @staticmethod
    def _request_json(url: str, data: dict[str, str] | None = None, access_token: str = "") -> dict[str, Any]:
        encoded = urlencode(data).encode("utf-8") if data is not None else None
        headers = {"Accept": "application/json", "User-Agent": "Music-HandControl/1.5"}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        request = Request(url, data=encoded, headers=headers, method="POST" if data is not None else "GET")
        try:
            with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed Spotify API endpoints only
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:180]
            if exc.code == 401:
                raise RuntimeError("Spotify session expired. Connect again to continue.") from exc
            raise RuntimeError(f"Spotify request failed ({exc.code}): {detail}") from exc
        except URLError as exc:
            raise RuntimeError("Could not reach Spotify. Check your internet connection.") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Spotify returned an unexpected response.")
        return payload

"""Cliente autenticado de terracodex-api.

Envía ``Authorization: Bearer <accessToken>``. Si el backend responde 401 (el access token dura 15 minutos),
renueva la sesión con el refresh token una sola vez y reintenta. Si tampoco se puede renovar, lanza
``SesionExpirada``: la UI debe volver al login.

Todos los métodos son bloqueantes: desde la UI llamarlos con ``asyncio.to_thread``.
"""

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

import config
from services import auth_service
from services.auth_service import _SSL, AuthError, Session, _message


class ApiError(Exception):
    """Error del API con un mensaje listo para mostrar al usuario."""


class SesionExpirada(ApiError):
    """La sesión ya no es válida (expiró o fue revocada). Hay que iniciar sesión otra vez."""


class _NoAutorizado(Exception):
    pass


class ApiClient:
    def __init__(self, session: Session, on_session_change: Callable[[Session], None] | None = None):
        self._session = session
        self._on_session_change = on_session_change
        self._lock = threading.Lock()

    @property
    def session(self) -> Session:
        return self._session

    def get(self, endpoint: str, params: dict | None = None, timeout: float | None = None):
        return self._request("GET", endpoint, params=params, timeout=timeout)

    def post(self, endpoint: str, payload: dict, timeout: float | None = None):
        return self._request("POST", endpoint, payload=payload, timeout=timeout)

    def delete(self, endpoint: str, timeout: float | None = None):
        return self._request("DELETE", endpoint, timeout=timeout)

    # ---------- interno ----------

    def _request(self, method, endpoint, payload=None, params=None, timeout=None):
        usada = self._session
        try:
            return self._enviar(method, endpoint, payload, params, timeout, usada)
        except _NoAutorizado:
            self._renovar(usada)
            try:
                return self._enviar(method, endpoint, payload, params, timeout, self._session)
            except _NoAutorizado as e:
                raise SesionExpirada("Tu sesión expiró. Inicia sesión nuevamente") from e

    def _renovar(self, usada: Session):
        with self._lock:
            if self._session is not usada:
                return  # otro hilo ya la renovó
            try:
                self._session = auth_service.refresh(usada)
            except AuthError as e:
                raise SesionExpirada("Tu sesión expiró. Inicia sesión nuevamente") from e
        if self._on_session_change:
            self._on_session_change(self._session)

    def _enviar(self, method, endpoint, payload, params, timeout, session: Session):
        url = f"{config.API_URL}{endpoint}"
        if params:
            query = {k: ("true" if v is True else "false" if v is False else v) for k, v in params.items() if v is not None}
            url = f"{url}?{urllib.parse.urlencode(query)}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json", **session.auth_header}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout or config.REQUEST_TIMEOUT, context=_SSL) as resp:
                body = resp.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            if e.code == 401:
                raise _NoAutorizado() from e
            if e.code == 503:
                raise ApiError(_message(body, "El servicio no está disponible. Intenta en unos minutos")) from e
            raise ApiError(_message(body, f"Error del servidor ({e.code})")) from e
        except TimeoutError as e:
            raise ApiError("El servidor tardó demasiado en responder. Intenta nuevamente") from e
        except (urllib.error.URLError, OSError) as e:
            raise ApiError("No se pudo conectar con el servidor. Revisa tu conexión a internet") from e

        try:
            data = json.loads(body) if body else {}
        except ValueError as e:
            raise ApiError("Respuesta inválida del servidor") from e
        if not isinstance(data, dict) or not data.get("ok", False):
            raise ApiError(_message(body, "Respuesta inválida del servidor"))
        return data.get("data")

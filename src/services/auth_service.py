"""Cliente de autenticación contra terracodex-api (Spring Boot).

Toda respuesta del backend tiene el formato ApiResponse:

    { "ok": true,  "status": 200, "message": "Bienvenido", "data": {...}, "timestamp": "..." }
    { "ok": false, "status": 401, "message": "Usuario o contraseña incorrectos", "errors": [...] }

Endpoints (públicos):

    POST /api/auth/login    {"login": "admin", "contrasena": "...", "canal": "WEB" | "MOVIL"}
    POST /api/auth/refresh  {"refreshToken": "..."}   -> nueva sesión; el refresh anterior deja de servir
    POST /api/auth/logout   {"refreshToken": "..."}

data de login/refresh:

    {"accessToken", "tokenType": "Bearer", "expiraEn", "refreshToken", "refreshExpiraEn",
     "usuario": {"id", "login", "descripcion", "avatar", "isWeb", "isMovil", "roles": [...]}}

El resto del API exige el header ``Authorization: Bearer <accessToken>`` (dura 15 minutos; se renueva con
``refresh``).
"""

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field

import config

try:
    import certifi

    # Certificados de certifi: el almacén de Windows y el Python empaquetado en Android no siempre reconocen la
    # cadena actual de Let's Encrypt (ISRG Root YE / X2) y la reportan como vencida.
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL = ssl.create_default_context()

CANAL_WEB = "WEB"
CANAL_MOVIL = "MOVIL"


class AuthError(Exception):
    """Error de autenticación con un mensaje listo para mostrar al usuario."""


@dataclass
class Session:
    token: str
    refresh_token: str
    user: dict = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.user.get("descripcion") or self.user.get("login") or "usuario"

    @property
    def roles(self) -> list[str]:
        return list(self.user.get("roles") or [])

    @property
    def auth_header(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}


def _message(body: bytes, default: str) -> str:
    """Mensaje de un ApiResponse de error; si hay errores por campo, los agrega."""
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return default
    if not isinstance(data, dict):
        return default
    message = data.get("message") or default
    errors = data.get("errors")
    if isinstance(errors, list) and errors:
        detalle = "; ".join(f"{e.get('field')}: {e.get('message')}" for e in errors if isinstance(e, dict))
        if detalle:
            message = f"{message} ({detalle})"
    return message


def _post(endpoint: str, payload: dict) -> dict:
    """POST JSON y devuelve el ``data`` del ApiResponse. Bloqueante."""
    request = urllib.request.Request(
        f"{config.API_URL}{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=config.REQUEST_TIMEOUT, context=_SSL) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read()
        if e.code in (400, 401, 403, 422):
            raise AuthError(_message(body, "Usuario o contraseña incorrectos")) from e
        raise AuthError(_message(body, f"Error del servidor ({e.code})")) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise AuthError("No se pudo conectar con el servidor") from e

    try:
        data = json.loads(body)
    except ValueError as e:
        raise AuthError("Respuesta inválida del servidor") from e
    if not isinstance(data, dict) or not data.get("ok"):
        raise AuthError(_message(body, "Respuesta inválida del servidor"))
    return data.get("data") or {}


def _session(data: dict) -> Session:
    token = data.get("accessToken")
    refresh_token = data.get("refreshToken")
    if not token or not refresh_token:
        raise AuthError("El servidor no devolvió los tokens de sesión")
    user = data.get("usuario") if isinstance(data.get("usuario"), dict) else {}
    return Session(token=token, refresh_token=refresh_token, user=user)


def login(usuario: str, contrasena: str, canal: str = CANAL_WEB) -> Session:
    """Inicia sesión. Bloqueante: desde la UI llamarlo con ``asyncio.to_thread``."""
    return _session(_post(config.LOGIN_ENDPOINT, {"login": usuario, "contrasena": contrasena, "canal": canal}))


def refresh(session: Session) -> Session:
    """Renueva el access token. Guarda la sesión devuelta: el refresh token anterior deja de servir."""
    return _session(_post(config.REFRESH_ENDPOINT, {"refreshToken": session.refresh_token}))


def logout(session: Session) -> None:
    """Cierra la sesión en el servidor. Si no hay conexión, se ignora: el token expira solo."""
    try:
        _post(config.LOGOUT_ENDPOINT, {"refreshToken": session.refresh_token})
    except AuthError:
        pass

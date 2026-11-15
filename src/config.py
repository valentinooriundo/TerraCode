import os

# URL base del backend (terracodex-api, Spring Boot). Por defecto, producción.
# Para desarrollo local: TERRACODE_API_URL=http://localhost:8080
API_URL = os.getenv("TERRACODE_API_URL", "https://api.rapiditto.com").rstrip("/")

# Endpoints de sesión relativos a API_URL (públicos: no exigen access token).
LOGIN_ENDPOINT = os.getenv("TERRACODE_LOGIN_ENDPOINT", "/api/auth/login")
REFRESH_ENDPOINT = os.getenv("TERRACODE_REFRESH_ENDPOINT", "/api/auth/refresh")
LOGOUT_ENDPOINT = os.getenv("TERRACODE_LOGOUT_ENDPOINT", "/api/auth/logout")
GOOGLE_INICIO_ENDPOINT = "/api/auth/google/inicio"
GOOGLE_SESION_ENDPOINT = "/api/auth/google/sesion"

# Explorador de TerraSprout (src/explorador.py, mapa y datos NASA). Solo en la versión web: si está vacío, el home no
# muestra la tarjeta. En el VPS: https://explorador.<dominio>/
EXPLORADOR_URL = os.getenv("TERRACODE_EXPLORADOR_URL", "").strip().rstrip("/")
if EXPLORADOR_URL and "://" not in EXPLORADOR_URL:  # solo el dominio (EXPLORADOR_DOMINIO del docker-compose)
    EXPLORADOR_URL = f"https://{EXPLORADOR_URL}"
EXPLORADOR_URL = f"{EXPLORADOR_URL}/" if EXPLORADOR_URL else ""

# Segundos máximos de espera por respuesta del backend.
REQUEST_TIMEOUT = float(os.getenv("TERRACODE_REQUEST_TIMEOUT", "10"))

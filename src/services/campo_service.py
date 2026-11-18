"""Registros de campo y recomendación de cultivos (módulo campo de terracodex-api).

    POST   /api/campo/recomendaciones  {"latitud", "longitud", "tipoRiego": "SECANO" | "GRAVEDAD" | "GOTEO"}
           -> {"zona": {...}, "cultivos": [{"codigo", "descripcion", "puntaje"}], "periodoReferencia", "errorMedio"}
    POST   /api/campo/registros        -> {"id"}
    GET    /api/campo/registros?page=&size=&search=&estado=&todos=
    DELETE /api/campo/registros/{id}   (anula, no borra)
"""

from services.api_client import ApiClient

TIPOS_RIEGO = {
    "SECANO": "Secano (lluvia)",
    "GRAVEDAD": "Riego por gravedad",
    "GOTEO": "Riego por goteo",
}

# La primera consulta de un punto descarga 30 años de clima de NASA POWER en el servidor
TIMEOUT_RECOMENDACION = 100


def recomendar(api: ApiClient, latitud: float, longitud: float, tipo_riego: str) -> dict:
    return api.post(
        "/api/campo/recomendaciones",
        {"latitud": latitud, "longitud": longitud, "tipoRiego": tipo_riego},
        timeout=TIMEOUT_RECOMENDACION,
    )


def registrar(api: ApiClient, registro: dict) -> int:
    return api.post("/api/campo/registros", registro)["id"]


def listar(api: ApiClient, page: int = 0, size: int = 20, search: str | None = None,
           estado: bool | None = None) -> dict:
    return api.get("/api/campo/registros", {"page": page, "size": size, "search": search, "estado": estado,
                                            "sort": "fechaRegistro,desc"})


def anular(api: ApiClient, registro_id: int) -> None:
    api.delete(f"/api/campo/registros/{registro_id}")

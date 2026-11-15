# TerraSprout

Explorador agrícola en Python y Flet para web y Android.

## Ejecutar la web

Con Python y uv instalados, desde la carpeta del proyecto:

```powershell
uv sync
uv run flet run --web --host 0.0.0.0 --port 8551 src/main.py
```

Abre la [portada](http://localhost:8551/) o el [mapa mundial](http://localhost:8551/mapa).
Usa «Mi ubicación» para consultar el GPS o «Buscar en el mapa» para buscar
una localidad. «Dibujar parcela» abre la edición del contorno.
Desde otro dispositivo en HTTP puedes seleccionar
la parcela manualmente. Para usar geolocalización desde otro dispositivo,
sirve la aplicación por HTTPS.

Si usas el Python de Windows en vez de uv, instala las dependencias y
arranca Flet con el mismo intérprete:

```powershell
py -m pip install -e . "flet[web,cli]==1.1.2"
& (Join-Path (py -c "import sysconfig; print(sysconfig.get_path('scripts'))") 'flet.exe') run --web --host 0.0.0.0 --port 8551 src/main.py
```

## Asistente agrícola web

Agrega estas variables al archivo local `.env` y reinicia Flet. La clave se
crea en [Google AI Studio](https://aistudio.google.com/apikey) y se configura
solo en el servidor.

```dotenv
GEMINI_API_KEY=tu_clave
GEMINI_MODEL=gemini-3.6-flash
```

Abre el botón de chat en Inicio, Mapa o Cultivos. Para recibir opciones
locales, selecciona una parcela en el mapa y pregunta qué sembrar o qué
escenario de agua evaluar. La respuesta usa el período de referencia del
predictor. Si Gemini no está disponible, el chat muestra las primeras
opciones calculadas por escenario cuando hay datos.

Para reutilizar el componente en una vista Flet, crea una instancia de
`AssistantView` por página web y pasa sus WebView a `attach`. Activa el botón
nativo cuando la vista carezca de lanzador HTML.
El selector de parcelas actualiza el contexto mediante `set_parcel`.

```python
from assistant_view import AssistantView

assistant = AssistantView(page)
assistant.attach()
assistant.button.visible = True
# Cuando el mapa confirme la selección:
assistant.set_parcel(latitude, longitude, label)
```

El historial se conserva en memoria durante la sesión de Flet. El servidor
limita las solicitudes a Gemini a 20 por minuto por proceso.

## Usar el explorador

1. Gira el globo de bienvenida, pulsa «Mi ubicación» o abre «Mapa» para
   seleccionar un punto. También puedes escribir coordenadas en «Análisis».
   El globo usa imágenes Blue Marble de NASA GIBS empaquetadas en WebP.
   El mapa interactivo carga sus teselas al abrirse.
2. Ajusta el período y consulta NASA POWER. Las tarjetas resumen siete
   variables diarias. El selector y el deslizador permiten inspeccionar cada día.
3. Abre ECOSTRESS para consultar las escenas de NASA Earthdata para el punto y
   las fechas. Pulsa «Ver imagen NASA» para cargar una miniatura disponible.
   Las escenas requieren revisión de nubes y calidad para su análisis.
4. En Parcela elige «Dibujar», toca los vértices en el mapa y pulsa «Cerrar
   contorno» para ver el área aproximada. El análisis científico usa el punto.
5. En Rotaciones compara tres secuencias según tus estimaciones de demanda de
   agua y cobertura del suelo. Los puntos son orientativos.

Fuentes: [NASA GIBS](https://nasa-gibs.github.io/gibs-api-docs/),
[POWER Daily](https://power.larc.nasa.gov/docs/services/api/temporal/daily/),
[CMR](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html)
y [ECOSTRESS](https://ecostress.jpl.nasa.gov/data).

## Proveedor de mapas

Copia `.env.example` a `.env` si el archivo todavía no existe.
`MAP_PROVIDER=OpenStreetMap` usa OpenStreetMap sin clave. El buscador usa Open-Meteo/GeoNames.

Para usar Google en el servidor Flet, configura `MAP_PROVIDER=Google`,
`GOOGLE_MAPS_API_KEY` y `GOOGLE_MAPS_REGION`, y reinicia el proceso.
Habilita Map Tiles API y facturación en Google Cloud. La clave viaja al
cliente para descargar las teselas, así que usa una clave restringida para
este uso. El mapa vuelve a OpenStreetMap si falla la sesión o la atribución.
El proveedor se elige una vez al abrir el mapa. Los cambios de cámara solo
actualizan la atribución y conservan la capa de teselas. Si quieres volver a
OpenStreetMap, cambia `MAP_PROVIDER=OpenStreetMap` y reinicia Flet.
La configuración de un APK requiere variables en su propio entorno.

`GLOBE_MODE=3d` activa Globe.GL en la web de Flet. Permite rotar con el
mouse o el dedo, acercar con la rueda o el pellizco y elegir un punto para
analizarlo. Usa `GLOBE_MODE=light` para iniciar con el globo local. La vista
nativa conserva el globo local.

[Google Map Tiles API](https://developers.google.com/maps/documentation/tile)

## Editar la portada

En `src/assets/landing/`, edita el texto en `inicio.html`, los estilos en
`styles.css` y los nombres y fotos en `equipo.json`. Los enlaces al explorador
son relativos a la instalación de Flet.

El encabezado muestra el divisor al pasar la sección del video. Para incluir
perfiles verificados, agrega el campo `linkedin` a los integrantes en
`equipo.json`.

Para usar el video oficial de YouTube, coloca su enlace en
`data-youtube-url` dentro de `inicio.html`. La portada carga el reproductor
cuando llega a la sección. Si no hay enlace, muestra el video local.

## Empaquetar Android

```powershell
uv run flet build apk
```

La app requiere acceso a internet para obtener las imágenes y datos.

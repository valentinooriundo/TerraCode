import asyncio
import logging
from os import getenv
from datetime import date, timedelta
from ipaddress import ip_address
from math import atan, ceil, degrees, log, pi, radians, sin, sinh, tan
from statistics import mean
from urllib.parse import urlencode, urlsplit

import flet as ft
import flet.canvas as cv
import flet_geolocator as gps
import flet_map as fm
import flet_webview as fwv

import nasa
import map_provider
from globe_view import GlobeView
from assistant_view import AssistantView
from crop_scene import crop_scene_controls
from parcel_report import parcel_pdf
from place_search import find_places, google_location, google_places, google_search_enabled
from uuid import uuid4

from ml import predictor
from ml import rotation as rotation_ml

MAP_START = (15, 0)
MAP_START_ZOOM = 2


def browser_url(url):
    parts = urlsplit(url or "")
    scheme = {"ws": "http", "wss": "https"}.get(parts.scheme, parts.scheme)
    return parts._replace(scheme=scheme)


def globe_document_url(url):
    parts = browser_url(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    return parts._replace(path="/earth3d.html",
                          query="", fragment="").geturl()


def web_location_allowed(url):
    origin = browser_url(url)
    if origin.scheme != "http":
        return True
    host = origin.hostname or ""
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


async def main(page: ft.Page):
    page.title = "TerraSprout · Explorador agrícola"
    page.theme = ft.Theme(color_scheme_seed="#21694E")
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#EFF4EF"
    page.padding = 0
    page.spacing = 0
    lang = "en" if page.web and page.query.to_dict.get("lang") == "en" else "es"
    def tr(es, en):
        return en if lang == "en" else es

    if page.web and urlsplit(page.route or "").path.rstrip("/") == "/asistente":
        params = page.query.to_dict
        chat = AssistantView(page, embedded=True, full_page=params.get("panel") != "1", lang=lang)
        point = params.get("punto", "")
        try:
            latitude, longitude = map(float, point.split(","))
        except (TypeError, ValueError):
            pass
        else:
            if -85 <= latitude <= 85 and -180 <= longitude <= 180:
                chat.set_parcel(latitude, longitude, (params.get("zona") or "Parcela seleccionada")[:120])
        await chat.mount_embedded()
        return
    assistant = AssistantView(page, lang=lang) if page.web else None
    origin = browser_url(page.url)
    project_url = origin._replace(path="/landing/inicio.html",
                                  query=f"lang={lang}" if "lang" in page.query.to_dict else "", fragment="").geturl()
    home_url = origin._replace(path="/", query=f"lang={lang}", fragment="").geturl()
    map_url = origin._replace(path="/mapa", query=f"lang={lang}", fragment="").geturl()
    chrome_url = origin._replace(path="/landing/chrome.html", query="", fragment="").geturl()
    globe_url = globe_document_url(page.url) if page.web and getenv("GLOBE_MODE", "3d") == "3d" else None
    use_3d = globe_url is not None

    geo = gps.Geolocator()
    page.services.append(geo)
    coords = ft.Text(tr("Toca el mapa para seleccionar la parcela.", "Tap the map to select a plot."), selectable=True)
    status = ft.Text()
    location_status = ft.Text(color="#FFFFFF", size=13)
    toast_job = None

    def notify(message, color="#173455", dismiss=True):
        nonlocal toast_job
        if toast_job:
            toast_job.cancel()
        location_status.value = message
        toast.bgcolor = color
        toast.visible = True
        page.update()

        async def hide():
            await asyncio.sleep(4)
            toast.visible = False
            page.update()

        toast_job = asyncio.create_task(hide()) if dismiss else None
    climate = ft.Column([ft.Text("Selecciona una parcela para consultar NASA POWER.")])
    satellite = ft.Column([ft.Text("Selecciona una parcela para buscar escenas ECOSTRESS.")])
    soil_panel = ft.Column([
        ft.Text("Selecciona una parcela para analizar el suelo.")
    ])
    crop_panel = ft.Column([
        ft.Text("Selecciona una parcela para evaluar cultivos.")
    ])
    rotation_panel = ft.Column(
        controls=[
            ft.Text("Selecciona una parcela para analizar rotaciones.")
        ]
    )
    lat = ft.TextField(label=tr("Latitud", "Latitude"), width=155)
    lon = ft.TextField(label=tr("Longitud", "Longitude"), width=155)
    end = ft.TextField(label="Hasta (AAAA-MM-DD)", value=str(date.today()), width=180)
    start = ft.TextField(label="Desde (AAAA-MM-DD)", value=str(date.today() - timedelta(days=89)), width=180)
    version = 0
    position_revision = 0
    locating = False
    drawing = False
    vertices = []
    saved_vertices = []
    selected_vertex = None
    scene_request = None
    climate_job = None
    scene_job = None
    selection_key = None

    async def choose(event):
        nonlocal selected_vertex
        point = fm.MapLatitudeLongitude(event.coordinates.latitude,
                                        (event.coordinates.longitude + 180) % 360 - 180)
        if drawing:
            if selected_vertex is None:
                if vertices and point == vertices[-1]:
                    return
                vertices.append(point)
            else:
                vertices[selected_vertex] = point
                selected_vertex = None
            update_boundary()
            return
        await select(point.latitude, point.longitude)

    marker = fm.MarkerLayer(markers=[])
    handles = fm.MarkerLayer(markers=[])
    outline = fm.PolylineLayer(polylines=[])
    boundary = fm.PolygonLayer(polygons=[])
    gps_accuracy = fm.CircleLayer(circles=[])
    last_camera = None

    def remember_camera(event):
        nonlocal last_camera
        last_camera = event.camera

    globe = fm.Map(
        expand=True, initial_center=fm.MapLatitudeLongitude(*MAP_START), initial_zoom=MAP_START_ZOOM,
        on_tap=choose, on_position_change=remember_camera, layers=[boundary, outline, marker, handles],
    )
    attribution = ft.Text(map_provider.OSM_CREDIT, color="#FFFFFF", size=12)
    credit_job = None
    google_credentials = None
    google_url = None
    active_provider = None
    provider_started = False
    provider_focus = None
    tiles = fm.TileLayer(url_template=map_provider.OSM_URL, keep_buffer=1, pan_buffer=0,
                         user_agent_package_name="TerraSprout/1.0")

    def set_basemap(provider, url, credit, zoom=19):
        nonlocal active_provider
        if provider != active_provider:
            tiles.url_template = url
            tiles.max_native_zoom = zoom
            if active_provider is None:
                globe.layers = [tiles, gps_accuracy, boundary, outline, marker, handles]
            active_provider = provider
        attribution.value = credit

    def osm_basemap():
        set_basemap("osm", map_provider.OSM_URL, map_provider.OSM_CREDIT)

    async def update_google_credit(camera, initial=False):
        if not initial:
            await asyncio.sleep(.5)
        point = camera.center if camera else provider_focus
        zoom = camera.zoom if camera else 13 if point else MAP_START_ZOOM
        latitude = point.latitude if point else MAP_START[0]
        longitude = point.longitude if point else MAP_START[1]
        margin = max(page.width or 800, page.height or 700) / (256 * 2 ** zoom)
        mercator = log(tan(pi / 4 + radians(max(-85, min(85, latitude))) / 2))
        north = degrees(atan(sinh(min(pi, mercator + pi * margin))))
        south = degrees(atan(sinh(max(-pi, mercator - pi * margin))))
        west, east = longitude - 180 * margin, longitude + 180 * margin
        if west < -180 or east > 180:
            west, east = -180, 180
        try:
            credit = await asyncio.to_thread(map_provider.google_credit, google_credentials,
                                             ceil(zoom), north, south, east, west)
        except Exception:
            if initial:
                osm_basemap()
                notify("Google Maps no está disponible. Mostrando OpenStreetMap.", "#775019")
        else:
            set_basemap("google", google_url, f"Google Maps · {credit}", zoom=22)
        page.update()

    async def track_camera(event):
        nonlocal last_camera, credit_job
        last_camera = event.camera
        if active_provider != "google" or event.event_type not in {
            fm.MapEventType.MOVE_END, fm.MapEventType.FLING_ANIMATION_END,
            fm.MapEventType.DOUBLE_TAP_ZOOM_END, fm.MapEventType.SCROLL_WHEEL_ZOOM,
            fm.MapEventType.NON_ROTATED_SIZE_CHANGE,
        }:
            return
        if credit_job and not credit_job.done():
            credit_job.cancel()
        credit_job = asyncio.create_task(update_google_credit(last_camera))

    async def load_provider():
        nonlocal google_url, google_credentials
        try:
            google_url, google_credentials = await asyncio.to_thread(map_provider.google_tiles)
        except Exception:
            osm_basemap()
            notify("Google Maps no está disponible. Mostrando OpenStreetMap.", "#775019")
            return
        await update_google_credit(last_camera, initial=True)
        if active_provider == "google":
            globe.on_event = track_camera
            page.update()

    def button(label, callback, icon=None):
        return ft.Button(label, on_click=callback, icon=icon, height=40,
                         style=ft.ButtonStyle(bgcolor="#17604A", color="#FFFFFF",
                                              shape=ft.RoundedRectangleBorder(radius=10)))

    async def locate(event=None):
        if drawing:
            notify("Cierra o cancela el dibujo antes de cambiar de lugar.", "#775019")
            return
        nonlocal position_revision, locating
        if locating:
            return
        if page.web and not web_location_allowed(page.url):
            show_map()
            notify("Activa HTTPS para usar el GPS o marca la parcela en el mapa.", "#775019")
            return
        locating = True
        position_revision += 1
        revision = position_revision
        location_button.disabled = True
        location_button.tooltip = tr("Buscando ubicación…", "Finding your location…")
        notify("Buscando ubicación… Si aparece el permiso, elige Permitir.", dismiss=False)
        try:
            # The browser requests permission through getCurrentPosition itself.
            if event is not None and not page.web:
                await asyncio.wait_for(geo.request_permission(), timeout=12)
            configuration = gps.GeolocatorWebConfiguration(
                accuracy=gps.GeolocatorPositionAccuracy.HIGH,
                time_limit=ft.Duration(seconds=20), maximum_age=ft.Duration(seconds=0),
            ) if page.web else None
            position = await asyncio.wait_for(geo.get_current_position(configuration), timeout=23)
        except TimeoutError:
            if revision == position_revision:
                show_map()
                notify("La ubicación tardó demasiado. Activa el GPS o marca la parcela.", "#775019")
            return
        except Exception as error:
            logging.getLogger(__name__).warning("Geolocalización: %s", error)
            if revision == position_revision:
                show_map()
                reason = str(error).lower()
                if "denied" in reason or "permission" in reason:
                    notify("Permite la ubicación en el navegador y el dispositivo.", "#775019")
                else:
                    notify("Ubicación no disponible. Activa el GPS o marca la parcela.", "#775019")
            return
        finally:
            locating = False
            location_button.disabled = False
            location_button.tooltip = tr("Mi ubicación", "My location")
            page.update()
        if revision == position_revision:
            if position.accuracy is None or not 0 < position.accuracy <= 100:
                show_map()
                notify("La ubicación es imprecisa. Busca tu zona o selecciona la parcela.", "#775019")
                return
            label = f"GPS · precisión ±{position.accuracy:.0f} m"
            notify("Ubicación recibida. Cargando datos de la zona.", "#146247")
            gps_accuracy.circles = [fm.CircleMarker(
                radius=max(1, position.accuracy), use_radius_in_meter=True,
                coordinates=fm.MapLatitudeLongitude(position.latitude, position.longitude),
                color="#334D9DF0", border_color="#4D9DF0", border_stroke_width=2,
            )]
            await select(position.latitude, position.longitude, label)

    async def manual(_):
        try:
            latitude, longitude = float(lat.value), float(lon.value)
        except ValueError:
            status.value = "Introduce latitud y longitud numéricas."
            page.update()
            return
        await select(latitude, longitude)

    report_data = None
    report_busy = False
    report_ready = False
    file_picker = ft.FilePicker() if page.web else None
    if file_picker:
        page.services.append(file_picker)

    async def download_report(_):
        nonlocal report_busy
        if not report_data or not report_ready or report_busy:
            return
        report_busy = True
        report_button.disabled = True
        page.update()
        snapshot = dict(report_data)
        try:
            content = await asyncio.to_thread(parcel_pdf, snapshot, lang)
            await file_picker.save_file(
                file_name=tr("TerraSprout-ficha-parcela.pdf", "TerraSprout-plot-factsheet.pdf"),
                file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["pdf"], src_bytes=content,
            )
        except Exception:
            logging.getLogger(__name__).exception("Could not export plot factsheet")
            notify(tr("No se pudo descargar la ficha PDF.", "Could not download the PDF."), "#75372B")
        finally:
            report_busy = False
            report_button.disabled = not report_ready
            page.update()

    report_button = ft.TextButton(
        tr("Imprimir ficha PDF", "Print plot PDF"), icon=ft.Icons.PRINT_OUTLINED,
        tooltip=tr("Descargar ficha técnica PDF", "Download plot factsheet PDF"),
        on_click=download_report, disabled=True,
        style=ft.ButtonStyle(bgcolor="#D8F88E", color="#102623"),
    )

    async def select(latitude, longitude, name="Parcela seleccionada"):
        nonlocal version, position_revision, scene_request, climate_job, scene_job, selection_key, provider_focus
        nonlocal report_data, report_ready
        if drawing:
            notify("Cierra o cancela el dibujo antes de cambiar de lugar.", "#775019")
            return
        position_revision += 1
        try:
            first, last = date.fromisoformat(start.value), date.fromisoformat(end.value)
            if not (-85 <= latitude <= 85 and -180 <= longitude <= 180):
                raise ValueError
            if not 0 <= (last - first).days <= 366:
                raise ValueError
        except ValueError:
            status.value = "Revisa las coordenadas y las fechas. El período máximo es de un año."
            page.update()
            return
        key = (round(latitude, 5), round(longitude, 5), first, last)
        if name == "Parcela seleccionada" and key == selection_key and climate_job and not climate_job.done():
            return
        selection_key = key
        report_ready = False
        report_button.disabled = True
        report_data = {"name": name, "latitude": latitude, "longitude": longitude, "start": first, "end": last}
        if assistant:
            assistant.set_parcel(latitude, longitude, name)
        for job in (climate_job, scene_job):
            if job and not job.done():
                job.cancel()
        version += 1
        current = version
        point = fm.MapLatitudeLongitude(latitude, longitude)
        provider_focus = point
        show_map()
        drawer.visible = True
        reopen_analysis.visible = False
        panel.content = climate
        highlight_tab("Clima")
        lat.value, lon.value = f"{latitude:.5f}", f"{longitude:.5f}"
        coords.value = f"{name} · {lat.value}, {lon.value}"
        if not name.startswith("GPS"):
            gps_accuracy.circles = []
            toast.visible = False
        status.value = ""
        marker.markers = [fm.Marker(coordinates=point, content=ft.Icon(ft.Icons.LOCATION_ON, color="#D55334", size=36))]
        climate.controls = [ft.ProgressBar(), ft.Text("Consultando NASA POWER…")]
        satellite.controls = [ft.Text("Abre ECOSTRESS para consultar las escenas de esta parcela.")]
        soil_panel.controls = [
            ft.ProgressBar(),
            ft.Text("Consultando humedad del suelo...")
        ]
        crop_panel.controls = [
            ft.ProgressBar(),
            ft.Text("Evaluando cultivos con Machine Learning...")
        ]
        rotation_panel.controls = [
            ft.ProgressBar(),
            ft.Text("Analizando alternativas de rotación...")
        ]
        page.update()
        async def focus():
            try:
                zoom = 16 if name.startswith("GPS") else 13 if name != "Parcela seleccionada" else None
                await asyncio.wait_for(globe.move_to(point, zoom=zoom), timeout=3)
            except Exception:
                pass

        async def update(panel, fetch, render, report_key=None):
            try:
                data = await asyncio.to_thread(fetch, latitude, longitude, first, last)
                if current == version:
                    panel.controls = render(data)
                    if report_key:
                        report_data[report_key] = data
            except Exception as error:
                logging.getLogger(__name__).warning("NASA %s: %s", fetch.__name__, type(error).__name__)
                if current == version:
                    async def retry(_):
                        if current != version:
                            return
                        panel.controls = [ft.ProgressBar(), ft.Text("Consultando NASA…")]
                        panel.update()
                        await update(panel, fetch, render, report_key)

                    panel.controls = [
                        ft.Text("NASA no respondió. Puedes reintentar esta consulta."),
                        ft.TextButton("Reintentar", on_click=retry),
                    ]
            if current == version:
                page.update()

        async def load_scenes():
            satellite.controls = [ft.ProgressBar(), ft.Text("Buscando escenas en NASA Earthdata…")]
            page.update()
            await update(satellite, nasa.scenes, scene_panel)

        scene_request = load_scenes
        async def load_climate():
            nonlocal report_ready
            await asyncio.sleep(.22)

            await asyncio.gather(
                focus(),
                update(climate, nasa.climate, climate_panel, "climate"),
                update(soil_panel, nasa.soil, render_soil, "soil"),
                update(crop_panel, predictor.compare, render_crop_scenarios, "crops"),
            )
            if current == version:
                report_ready = True
                report_button.disabled = report_busy
                page.update()
        climate_job = asyncio.create_task(load_climate())

    def climate_panel(data):
        def display_units(code):
            raw = data.get("parameters", {}).get(code, {}).get("units", "")
            return {"C": "°C", "MJ/m^2/day": "MJ/m²/día",
                    "mm/day": "mm/día", "kW-hr/m^2/day": "kWh/m²/día"}.get(raw, raw)

        daily = {code: nasa.daily(data, code) for code in nasa.METRICS}
        rainfall = daily["PRECTOTCORR"]
        tiles = []
        for code, label in nasa.METRICS.items():
            values = [value for _, value in daily[code] if value is not None]
            units = display_units(code)
            if code == "PRECTOTCORR":
                label, units, aggregate = "Lluvia acumulada", "mm", sum
            else:
                aggregate = {"T2M_MIN": min, "T2M_MAX": max}.get(code, mean)
            text = f"{aggregate(values):.2f} {units}" if values else "Sin datos"
            tiles.append(card(label, text))
        valid_rain = sum(value is not None for _, value in rainfall)
        tiles.append(card("Racha seca (< 1 mm/día)", f"{nasa.dry_spell(rainfall)} días" if valid_rain else "Sin datos"))
        detail = ft.Text(selectable=True, color="#173B2D", weight=ft.FontWeight.W_600)
        scale = ft.Text(size=12, color="#3F6354")
        chart = cv.Canvas(height=122)
        chart_width = 240
        day_slider = ft.Slider(min=0, max=1, value=0)
        metric = ft.Dropdown(
            label="Explorar serie diaria", value="T2M",
            options=[ft.DropdownOption(key=key, text=label) for key, label in nasa.METRICS.items()],
        )

        def show_day(_=None):
            values = daily[metric.value]
            day_slider.max = max(1, len(values) - 1)
            day_slider.divisions = max(1, len(values) - 1)
            day_slider.disabled = len(values) <= 1
            day_slider.value = min(int(day_slider.value), max(0, len(values) - 1))
            if not values:
                detail.value = "Sin datos para esta variable."
                scale.value = ""
                chart.shapes = []
                return
            day, value = values[int(day_slider.value)]
            units = display_units(metric.value)
            detail.value = f"{day} UTC · " + ("Sin dato" if value is None else f"{value:.2f} {units}")
            valid = [v for _, v in values if v is not None]
            if not valid:
                scale.value = ""
                chart.shapes = []
                return
            low, high = min(valid), max(valid)
            scale.value = f"Rango observado · {low:.2f} a {high:.2f} {units}"
            x = lambda i: 8 + (chart_width - 16) * i / max(1, len(values) - 1)
            y = lambda v: 108 - 94 * (v - low) / (high - low) if high != low else 61
            line = ft.Paint(color="#238365", stroke_width=2)
            grid = ft.Paint(color="#D1E5D9", stroke_width=1)
            chart.shapes = [cv.Line(8, h, chart_width - 8, h, grid) for h in (14, 61, 108)]
            for i in range(1, len(values)):
                a, b = values[i - 1][1], values[i][1]
                if a is not None and b is not None and (values[i][0] - values[i - 1][0]).days == 1:
                    chart.shapes.append(cv.Line(x(i - 1), y(a), x(i), y(b), line))
            if value is not None:
                chart.shapes.append(cv.Circle(x(int(day_slider.value)), y(value), 4, ft.Paint(color="#D65F3A")))

        def chart_resize(event):
            nonlocal chart_width
            if abs(chart_width - event.width) < 1:
                return
            chart_width = max(17, event.width)
            show_day()
            chart.update()

        chart.on_resize = chart_resize
        def changed(event):
            show_day(event)
            page.update()

        metric.on_select = changed
        day_slider.on_change_end = changed
        show_day()
        return [
            ft.Text(f"NASA POWER · resolución regional · {valid_rain} días con datos de lluvia"),
            ft.ResponsiveRow(tiles), metric,
            ft.Container(content=ft.Column([chart, scale], spacing=4,
                         horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                         padding=10, bgcolor="#EDF6F1", border_radius=12),
            day_slider, detail,
        ]

    def render_soil(data):
        tiles = []

        for code, label in nasa.SOIL_METRICS.items():
            values = [
                value
                for _, value in nasa.daily(data, code)
                if value is not None and 0 <= value <= 1
            ]

            value = (
                f"{mean(values):.2f} / 1"
                if values
                else "Sin datos"
            )

            tiles.append(card(label, value))

        return [
            ft.Text(
                "Análisis hídrico del suelo",
                size=20,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Text("NASA POWER · Datos regionales"),
            ft.ResponsiveRow(tiles),
            ft.Text(
                "Los valores representan humedad relativa "
                "del suelo en una escala de 0 a 1.",
                size=12,
            ),
        ]

    def crop_preview_controls(code, scenario, scores):
        if page.web:
            return crop_scene_controls(page, code, scenario, scores, preferences=assistant.preferences,
                                       height=190, lang=lang)
        return [ft.Text(" · ".join(f"{mode}: {score:g}/100" for mode, score in scores.items()), size=12)]

    def render_crop_scenarios(data):
        rotation_panel.controls = render_rotation_scenarios(data)
        names, scores = {}, {}
        water_labels = {
            "rainfed": tr("Secano", "Rainfed"),
            "irrigated_gravity": tr("Gravedad", "Gravity"),
            "irrigated_drip": tr("Goteo", "Drip"),
        }
        for scenario, result in data.items():
            for item in result["recommendations"]:
                if item["score"] > 0:
                    names[item["code"]] = item["crop"]
                    scores.setdefault(item["code"], {})[scenario] = item["score"]
        period = next((value.get("reference_period") for value in data.values() if value.get("reference_period")), "")
        controls = [
            ft.Text(tr("Aptitud por cultivo", "Suitability by crop"), size=20, weight=ft.FontWeight.BOLD),
            ft.Text(tr("Escenarios con puntuación positiva · NASA POWER", "Positive-score scenarios · NASA POWER"), size=12),
            ft.Text(period, size=12, color="#285344"),
        ]
        for code, by_water in sorted(scores.items(), key=lambda pair: (-max(pair[1].values()), names[pair[0]])):
            best = max(by_water, key=by_water.get)
            controls.append(ft.Container(
                bgcolor="#E4F2E9", padding=12, border_radius=12,
                content=ft.Column([
                    ft.Text(names[code], size=18, weight=ft.FontWeight.BOLD),
                    *crop_preview_controls(code, best, by_water),
                ], spacing=5),
            ))
        if not scores:
            controls.append(ft.Text(tr("Ningún cultivo obtuvo una puntuación positiva en este punto.",
                                       "No crop received a positive score at this point.")))
        avocado = [
            f"{water_labels[scenario]} · {result['avocado_gaez_v5']:.2f}/100"
            for scenario, result in data.items() if (result.get("avocado_gaez_v5") or 0) > 0
        ]
        if avocado:
            controls.append(ft.Container(
                bgcolor="#E4F2E9", padding=12, border_radius=12,
                content=ft.Column([ft.Text(tr("Palta", "Avocado"), size=18, weight=ft.FontWeight.BOLD),
                                   ft.Text(" · ".join(avocado)), ft.Text("FAO GAEZ V5 · 2001-2020", size=12)]),
            ))
        controls.append(ft.Text(tr("La puntuación orienta la comparación. Confirma el agua disponible en campo.",
                                   "Scores help compare options. Confirm water availability in the field."), size=12))
        return controls

    def render_rotation_scenarios(data):

        results = ft.Column()

        crop_selector = ft.Dropdown(
            label="Cultivo anterior",
            value="mze",
            options=[
                ft.DropdownOption(
                    key=item["code"],
                    text=item["crop"],
                )
                for item in sorted(
                    data["rainfed"]["recommendations"],
                    key=lambda item: item["crop"],
                )
            ],
        )

        water_selector = ft.Dropdown(
            label="Sistema de suministro de agua",
            value="rainfed",
            options=[
                ft.DropdownOption(
                    key="rainfed",
                    text="Secano",
                ),
                ft.DropdownOption(
                    key="irrigated_gravity",
                    text="Riego por gravedad",
                ),
                ft.DropdownOption(
                    key="irrigated_drip",
                    text="Riego por goteo",
                ),
            ],
        )

        def calculate():

            result = rotation_ml.recommend_rotations(
                data[water_selector.value],
                previous_crop=crop_selector.value,
            )
            if report_data is not None:
                report_data["rotation"] = result
            controls = [
                ft.Text(
                    result["message"],
                    weight=ft.FontWeight.BOLD,
                )
            ]

            if result["status"] == "insufficient":

                controls.append(
                    ft.Text(
                        "No se recomienda iniciar una "
                        "rotación bajo estas condiciones.",
                        color="#B45309",
                    )
                )

            for item in result["next_crops"]:

                controls.append(
                    ft.Container(
                        bgcolor="#E4F2E9",
                        padding=15,
                        border_radius=12,
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    item["crop"],
                                    size=18,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(
                                    f"Aptitud: {item['score']:.2f}/100"
                                ),
                                ft.Text(item["reason"]),
                                *crop_preview_controls(item["code"], water_selector.value,
                                                       {water_selector.value: item["score"]}),
                            ]
                        ),
                    )
                )

            if result["plans"]:

                controls.append(
                    ft.Text(
                        "Secuencias propuestas",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                    )
                )

            for plan in result["plans"]:

                controls.append(
                    ft.Container(
                        bgcolor="#E4F2E9",
                        padding=15,
                        border_radius=12,
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    " → ".join(plan["crops"]),
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(
                                    f"Aptitud mínima: "
                                    f"{plan['minimum_suitability']:.2f}/100"
                                ),
                            ]
                        ),
                    )
                )

            results.controls = controls

        async def analyze(e):
            calculate()
            page.update()

        crop_selector.on_select = analyze
        water_selector.on_select = analyze

        calculate()

        return [
            ft.Text(
                "Planificador de rotación agrícola",
                size=22,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Text(
                "TerraSprout AI · Machine Learning y agronomía",
                color="#17604A",
            ),
            crop_selector,
            water_selector,
            ft.Divider(),
            results,
            ft.Text(
                "Propuesta experimental. Requiere validar "
                "el calendario agrícola y la disponibilidad de agua.",
                size=11,
            ),
        ]

    def scene_panel(entries):
        if not entries:
            return [ft.Text("NASA Earthdata no encontró escenas para este punto y período.")]
        controls = [ft.Text(f"{len(entries)} escenas candidatas · ECO_L2T_LSTE v002. Verifica nubes y calidad.")]
        for scene in entries:
            title = scene.get("title", "")
            # NASA CMR distinguishes browse imagery from protected science files.
            browse_urls = [
                link["href"] for link in scene.get("links", [])
                if link.get("rel", "").endswith("/browse#") and link.get("href", "").startswith("https://")
                and link["href"].lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            thermal = next((url for url in browse_urls if url.lower().endswith("_lst.jpeg")), None)
            browse = thermal or next(iter(browse_urls), None)
            children = [
                ft.Text(scene.get("time_start", "")[:16].replace("T", " ") + " UTC", weight=ft.FontWeight.BOLD),
                ft.Text(title, selectable=True),
                ft.TextButton("Abrir registro de NASA Earthdata",
                              url=f"https://cmr.earthdata.nasa.gov/search/concepts/{scene['id']}.umm_json"),
            ]
            if browse:
                preview = ft.Container()

                async def toggle_preview(event, target=preview, image_url=browse):
                    trigger = event.control
                    if target.content is None or isinstance(target.content, ft.Text):
                        target.content = ft.ProgressBar()
                        trigger.disabled = True
                        page.update()
                        try:
                            image = await asyncio.to_thread(nasa.preview_image, image_url)
                            target.content = ft.Image(src=image, height=180, fit=ft.BoxFit.CONTAIN,
                                                      error_content=ft.Text("Imagen no compatible."))
                            trigger.content = "Ocultar imagen"
                        except Exception:
                            target.content = ft.Text("NASA no entregó esta miniatura. Abre el registro para revisarla.")
                            trigger.content = "Reintentar imagen"
                        finally:
                            trigger.disabled = False
                    else:
                        target.content = None
                        trigger.content = "Ver imagen NASA"
                    page.update()

                children.extend([ft.TextButton("Ver imagen NASA", on_click=toggle_preview), preview])
            controls.append(ft.Container(content=ft.Column(children), padding=12, bgcolor="#F3F7F3", border_radius=12))
        return controls

    def card(label, value):
        return ft.Container(
            col=6, bgcolor="#E4F2E9", border_radius=12, padding=12,
            content=ft.Column([ft.Text(label, size=12, color="#305B47"),
                              ft.Text(value, size=20, color="#123C2A", weight=ft.FontWeight.BOLD)]),
        )

    rotation = ft.Column()
    priority = ft.Dropdown(
        label="Prioridad", value="water",
        options=[ft.DropdownOption(key=k, text=v) for k, v in
                 [("water", "Ahorrar agua"), ("soil", "Cubrir el suelo"), ("equal", "Equilibrar")]],
    )
    options = []
    for label in ("Rotación actual", "Alternativa A", "Alternativa B"):
        sequence = ft.TextField(label=label, hint_text="Cultivo → cultivo de cobertura")
        levels = [ft.DropdownOption(key=str(i), text=name) for i, name in enumerate(("Baja", "Media", "Alta"))]
        water = ft.Dropdown(label="Demanda de agua", width=168, options=levels)
        cover = ft.Dropdown(label="Cobertura del suelo", width=168,
                            options=[ft.DropdownOption(key=item.key, text=item.text) for item in levels])
        options.append((sequence, water, cover))
        rotation.controls.extend([sequence, ft.Row([water, cover], wrap=True)])
    result = ft.Text(selectable=True)

    def compare(_):
        if any(not name.value.strip() or water.value is None or cover.value is None for name, water, cover in options):
            result.value = "Completa las secuencias, la demanda y la cobertura de las tres opciones."
        else:
            w, c = {"water": (2, 1), "soil": (1, 2), "equal": (1, 1)}[priority.value]
            ranked = sorted(
                [((2 - int(water.value)) * w + int(cover.value) * c, name.value.strip())
                 for name, water, cover in options], key=lambda item: item[0], reverse=True,
            )
            lines = [f"{name} · {score} puntos" for score, name in ranked]
            result.value = "\n".join(lines + [f"Peso del agua: {w}. Peso de la cobertura: {c}."])
        page.update()

    rotation.controls = [
        ft.Text("Evalúa la demanda de agua y la cobertura con los datos de tu finca."),
        priority, *rotation.controls, button("Comparar rotaciones", compare), result,
    ]
    parcel_status = ft.Text("Dibuja el perímetro tocando el mapa. El área es aproximada.")
    draw_tools = ft.Container(visible=False)
    draw_hint = ft.Text(size=12, color="#285344")

    def pick_vertex(index):
        def pick(_):
            nonlocal selected_vertex
            if drawing:
                selected_vertex = index
                update_boundary()
        return pick

    def update_boundary():
        outline.polylines = [fm.PolylineMarker(coordinates=vertices.copy(), color="#17604A",
                                              stroke_width=4)] if drawing and len(vertices) >= 2 else []
        finish_button.disabled = len({(p.latitude, p.longitude) for p in vertices}) < 3
        undo_button.disabled = not vertices
        handles.markers = [
            fm.Marker(coordinates=point, width=34, height=34, content=ft.Container(
                on_click=pick_vertex(i - 1), bgcolor="#B65C22" if selected_vertex == i - 1 else "#155840",
                border_radius=17, alignment=ft.Alignment.CENTER,
                content=ft.Text(str(i), size=12, color="#FFFFFF"),
            )) for i, point in enumerate(vertices, 1)
        ]
        count = len(vertices)
        parcel_status.value = tr(f"{count} vértices.", f"{count} vertices.") if drawing else tr(
            "Dibuja el perímetro tocando el mapa.", "Tap the map to draw a boundary."
        )
        draw_hint.value = (
            tr(f"Toca la nueva posición del vértice {selected_vertex + 1}.",
               f"Tap the new position for vertex {selected_vertex + 1}.")
            if selected_vertex is not None else
            tr(f"{count} vértices. Toca el mapa para añadir o un número para moverlo.",
               f"{count} vertices. Tap the map to add one or a number to move it.")
        )
        page.update()

    def draw_parcel(_):
        nonlocal drawing, selected_vertex, position_revision
        if drawing:
            return
        position_revision += 1
        toast.visible = False
        drawing = True
        selected_vertex = None
        draw_tools.visible = True
        vertices[:] = saved_vertices
        boundary.polygons = []
        drawer.visible = False
        reopen_analysis.visible = False
        show_map()
        update_boundary()

    def undo(_):
        nonlocal selected_vertex
        if drawing and vertices:
            selected_vertex = None
            vertices.pop()
            update_boundary()

    def cancel_draw(_):
        nonlocal drawing, selected_vertex
        drawing = False
        selected_vertex = None
        draw_tools.visible = False
        vertices.clear()
        handles.markers = []
        if saved_vertices:
            show_boundary(saved_vertices)
        drawer.visible = True
        update_boundary()
        if saved_vertices:
            parcel_status.value = "Edición cancelada. Se conservó el perímetro anterior."
            page.update()

    def show_boundary(points):
        boundary.polygons = [fm.PolygonMarker(coordinates=points.copy(), color="#4434D399",
                           border_color="#34D399", border_stroke_width=3)]

    def finish_parcel(_):
        nonlocal drawing, selected_vertex
        if not drawing or len({(p.latitude, p.longitude) for p in vertices}) < 3:
            draw_hint.value = tr("Añade al menos tres vértices distintos.", "Add at least three distinct vertices.")
            page.update()
            return
        pairs = list(zip(vertices, vertices[1:] + vertices[:1]))
        area = abs(sum(
            radians((b.longitude - a.longitude + 180) % 360 - 180)
            * (sin(radians(a.latitude)) + sin(radians(b.latitude))) for a, b in pairs
        )) * 6371008.8 ** 2 / 2
        if area < 1:
            draw_hint.value = tr("El contorno no encierra área suficiente. Ajusta los vértices.",
                                 "The boundary encloses too little area. Adjust the vertices.")
            page.update()
            return
        drawing = False
        selected_vertex = None
        draw_tools.visible = False
        outline.polylines = []
        handles.markers = []
        saved_vertices[:] = vertices
        show_boundary(saved_vertices)
        drawer.visible = True
        panel.content = parcel
        highlight_tab("Parcela")
        parcel_status.value = f"Área aproximada: {area / 10000:.3f} ha · {len(vertices)} vértices."
        page.update()

    parcel = ft.Column([
        ft.Text("Delimitar parcela", size=20, weight=ft.FontWeight.BOLD), parcel_status,
        button("Dibujar o editar parcela", draw_parcel),
        ft.Text("Clima y ECOSTRESS se consultan para el punto seleccionado."),
    ])
    panels = {
        "Clima": climate,
        "Suelo": soil_panel,
        "ECOSTRESS": satellite,
        "Parcela": parcel,
        "Cultivos": crop_panel,
        "Rotaciones": rotation_panel,
    }
    if page.web:
        panels = {name: panels[name] for name in ("Clima", "Suelo", "Cultivos", "Rotaciones")}
    panel = ft.Container(content=climate, bgcolor="#FFFFFF", padding=18, border_radius=16)
    crop_results_panel = ft.Container(content=crop_panel, bgcolor="#FFFFFF", padding=14, border_radius=14) if page.web else None
    active_tabs = {"left": "Clima", "right": "Cultivos"}

    def panel_side(name):
        return "right" if page.web and name in {"Cultivos", "Rotaciones"} else "left"

    def highlight_tab(name):
        active_tabs[panel_side(name)] = name
        for tab in tabs:
            active = tab.data == active_tabs[panel_side(tab.data)]
            tab.style = ft.ButtonStyle(bgcolor="#17604A" if active else "#E3EFE8",
                                       color="#FFFFFF" if active else "#214D3A")

    async def show_panel(event):
        nonlocal scene_request, scene_job
        name = event.control.data
        target = crop_results_panel if panel_side(name) == "right" else panel
        target.content = panels[name]
        highlight_tab(event.control.data)
        page.update()
        if event.control.data == "ECOSTRESS" and scene_request:
            fetch_scenes, scene_request = scene_request, None
            scene_job = asyncio.create_task(fetch_scenes())

    location_button = ft.IconButton(
        ft.Icons.MY_LOCATION, on_click=locate, tooltip=tr("Mi ubicación", "My location"),
        bgcolor="#E8F6FF", icon_color="#123250",
        visible=not use_3d,
    )
    async def select_from_globe(latitude, longitude):
        await select(latitude, longitude, "Punto seleccionado en el globo")

    welcome = GlobeView(on_point=select_from_globe)
    web_globe = fwv.WebView(url=globe_url, expand=True) if use_3d else None
    map_area = ft.Container(top=0, bottom=0, left=0, right=0, visible=False)
    welcome_layer = ft.Container(content=web_globe or welcome, top=0, bottom=0, left=0, right=0)

    def toggle_globe(_):
        welcome_layer.content = welcome if welcome_layer.content is web_globe else web_globe
        location_button.visible = welcome_layer.content is welcome
        page.update()

    def show_map():
        nonlocal provider_started
        if map_area.content is None:
            map_area.content = globe
        if not provider_started:
            provider_started = True
            if map_provider.google_requested():
                attribution.value = "Cargando Google Maps…"
                asyncio.create_task(load_provider())
            else:
                osm_basemap()
        welcome_layer.visible = False
        map_area.visible = True
        attribution.visible = True
        map_credit.visible = True
        map_toolbar.visible = True
        explore_button.visible = False
        location_button.visible = True
        globe_switch.visible = False

    def return_to_globe(_):
        if drawing:
            cancel_draw(None)
        drawer.visible = False
        map_area.visible = False
        map_credit.visible = False
        map_toolbar.visible = False
        explore_button.visible = True
        location_button.visible = welcome_layer.content is not web_globe or not use_3d
        welcome_layer.visible = True
        globe_switch.visible = use_3d
        page.update()

    def open_drawer(_):
        drawer.visible = True
        reopen_analysis.visible = False
        page.update()

    def close_drawer(_):
        drawer.visible = False
        reopen_analysis.visible = True
        page.update()

    attribution.visible = False
    for field in (lat, lon, start, end):
        field.col = 6
        field.width = None
    panel_names_en = {"Clima": "Climate", "Suelo": "Soil", "Parcela": "Plot",
                      "Cultivos": "Crops", "Rotaciones": "Rotations"}
    tabs = [ft.TextButton(tr(name, panel_names_en.get(name, name)), data=name, on_click=show_panel)
            for name in panels]
    highlight_tab("Clima")
    content_scroll = ft.Column([
        panel,
        ft.ExpansionTile(title=ft.Text(tr("Coordenadas y fechas", "Coordinates and dates")), controls=[
            ft.Container(padding=ft.Padding.symmetric(vertical=10), content=ft.Column([
                ft.ResponsiveRow([lat, lon, start, end], spacing=8, run_spacing=12),
                button(tr("Aplicar cambios", "Apply changes"), manual), status,
            ])),
        ]),
    ], scroll=ft.ScrollMode.AUTO, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    drawer = ft.Container(
        width=420, visible=page.web, bgcolor="#EAF2EB" if page.web else "#F3F7F3", padding=13,
        border_radius=16 if page.web else None,
        content=ft.Column([
            ft.Row([ft.Text(tr("Clima y suelo", "Climate and soil") if page.web else
                            tr("Análisis de parcela", "Plot analysis"), size=19, weight=ft.FontWeight.BOLD, expand=True),
                    *([] if page.web else [ft.IconButton(ft.Icons.CLOSE, tooltip="Cerrar panel", on_click=close_drawer)])],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            coords,
            *([report_button] if page.web else []),
            ft.Row([tab for tab in tabs if panel_side(tab.data) == "left"], wrap=True, spacing=5, run_spacing=5),
            content_scroll,
        ], expand=True),
    )
    if page.web:
        crop_drawer = ft.Container(
            bgcolor="#EAF2EB", padding=13, border_radius=16,
            content=ft.Column([
                ft.Text(tr("Cultivos y rotaciones", "Crops and rotations"), size=19, weight=ft.FontWeight.BOLD),
                ft.Row([tab for tab in tabs if panel_side(tab.data) == "right"], wrap=True, spacing=5),
                ft.Column([crop_results_panel], scroll=ft.ScrollMode.AUTO, expand=True,
                          horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            ], expand=True),
        )
    map_credit = ft.Container(left=12, bottom=10, right=92, visible=False,
                              alignment=ft.Alignment.CENTER_LEFT, content=ft.Container(
                                  bgcolor="#18382D", padding=7, border_radius=8, content=attribution,
                              ))
    draw_tools.left, draw_tools.right, draw_tools.bottom = 8, 8, 88
    draw_tools.padding, draw_tools.bgcolor, draw_tools.border_radius = 8, "#FFFFFF", 10
    finish_button = button(tr("Guardar contorno", "Save boundary"), finish_parcel)
    undo_button = ft.IconButton(ft.Icons.UNDO, tooltip=tr("Quitar último vértice", "Undo last vertex"), on_click=undo)
    draw_tools.content = ft.Column([ft.Text(tr("Dibujar parcela", "Draw plot"), weight=ft.FontWeight.BOLD), draw_hint, ft.Row([
        undo_button,
        finish_button,
        ft.TextButton(tr("Cancelar", "Cancel"), on_click=cancel_draw),
    ], wrap=True)], tight=True, spacing=2)
    toast = ft.Container(top=65, right=12, width=300, padding=12, border_radius=12,
                         content=location_status, visible=False, ignore_interactions=True)
    map_stack = ft.Stack([
        ft.Image(src="space.svg", left=0, right=0, top=0, bottom=0, fit=ft.BoxFit.COVER),
        welcome_layer, map_area,
        map_credit,
        *([] if page.web else [draw_tools]),
        ft.Container(right=22, bottom=38, content=location_button),
        toast,
    ], expand=True)
    globe_switch = ft.Container(
        left=12, bottom=72, visible=use_3d,
        content=ft.IconButton(ft.Icons.LAYERS_OUTLINED, tooltip="Cambiar vista del globo",
                              on_click=toggle_globe, bgcolor="#152940", icon_color="#E5F3FF"),
    )
    map_stack.controls.insert(-1, globe_switch)
    map_surface = ft.Container(
        content=map_stack, bgcolor="#030610", expand=True,
        border_radius=16 if page.web else None, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )
    compact_layout = None

    def resize(_=None):
        nonlocal compact_layout
        if not provider_started:
            globe.initial_zoom = max(MAP_START_ZOOM, ceil(log(max(256, page.width or 800) / 256, 2)))
        compact = bool(page.width and page.width < (1060 if page.web else 760))
        drawer.width = None if compact else min(460, max(330, (page.width or 1100) * .35))
        if page.web:
            width = page.width or 800
            header_view.height = 138 if width <= 510 else 112 if width <= 800 else 73
            drawer.width = None if compact else min(330, max(244, width * .23))
            crop_drawer.width = None if compact else drawer.width
            map_surface.height = max(360, min(560, (page.height or 800) * .66)) if compact else None
            map_surface.expand = not compact
            drawer.height = crop_drawer.height = 470 if compact else None
        else:
            drawer.height = min(500, (page.height or 700) * .57) if compact else None
        toast.width = min(300, max(140, (page.width or 800) - 24))
        if compact != compact_layout:
            if page.web:
                root.content = ft.Column(
                    [map_surface, drawer, crop_drawer], spacing=10, scroll=ft.ScrollMode.AUTO,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                ) if compact else ft.Row(
                    [drawer, map_surface, crop_drawer], spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                )
            else:
                layout_type = ft.Column if compact else ft.Row
                root.content = layout_type([map_surface, drawer], expand=True, spacing=0)
            compact_layout = compact
        welcome.resize_globe(page.width or 800, page.height or 700)
        page.update()

    root = ft.Container(expand=True, padding=10 if page.web else 0,
                        bgcolor="#081B18" if page.web else None)
    place_input = ft.TextField(hint_text=tr("Buscar ciudad o localidad", "Search for a city or town"), prefix_icon=ft.Icons.SEARCH,
                               border=ft.OutlineInputBorder(border_radius=24),
                               dense=True, autofocus=True, expand=True)
    place_results = ft.Column(scroll=ft.ScrollMode.AUTO, height=230)
    search_version = 0
    search_token = ""
    search_credit = ft.Text(size=12)

    async def search_places(_, immediate=False):
        nonlocal search_version, search_token
        search_version += 1
        current_search = search_version
        query = place_input.value.strip()
        if len(query) < 2:
            place_results.controls = []
            page.update()
            return
        if not immediate:
            await asyncio.sleep(.35)
            if current_search != search_version:
                return
        place_results.controls = [ft.Text("Buscando lugares…")]
        page.update()
        using_google = active_provider == "google" and google_search_enabled()
        try:
            if using_google:
                matches = await asyncio.to_thread(google_places, query, search_token)
            else:
                matches = await asyncio.to_thread(find_places, query)
        except Exception:
            matches = None
            if using_google:
                try:
                    matches = await asyncio.to_thread(find_places, query)
                    using_google = False
                except Exception:
                    pass
        if current_search != search_version:
            return
        search_credit.value = "Google Maps" if using_google else "Open-Meteo · GeoNames"
        place_results.controls = []
        for place in matches or []:
            name = place["name"]
            context = ", ".join(dict.fromkeys(place[key] for key in ("admin1", "country")
                                              if place.get(key) and place[key] != name))
            label = ", ".join(filter(None, (name, context)))

            async def choose_place(event, result=place, title=label):
                nonlocal search_version, search_token
                search_version += 1
                choice = search_version
                if "place_id" in result:
                    search_token = str(uuid4())
                    place_results.controls = [ft.ProgressBar(), ft.Text("Abriendo lugar…")]
                    page.update()
                    try:
                        latitude, longitude = await asyncio.to_thread(
                            google_location, result["place_id"], result["session_token"],
                        )
                    except Exception:
                        if choice == search_version:
                            place_results.controls = [ft.Text("Google no pudo abrir este lugar. Busca de nuevo.")]
                            page.update()
                        return
                else:
                    latitude, longitude = result["latitude"], result["longitude"]
                if choice != search_version:
                    return
                page.pop_dialog()
                await select(latitude, longitude, title)

            place_results.controls.append(ft.ListTile(
                leading=ft.Icon(ft.Icons.LOCATION_ON_OUTLINED, color="#17604A"),
                title=ft.Text(name, weight=ft.FontWeight.W_600),
                subtitle=ft.Text(context) if context else None,
                on_click=choose_place,
            ))
        if not matches:
            place_results.controls = [ft.Text("La búsqueda no respondió. Reintenta." if matches is None else "No hay coincidencias. Prueba con el país.")]
        page.update()

    def close_search(_):
        nonlocal search_version
        search_version += 1
        page.pop_dialog()

    async def submit_search(event):
        await search_places(event, immediate=True)

    place_input.on_change = search_places
    place_input.on_submit = submit_search
    search_dialog = ft.AlertDialog(
        modal=True, title=ft.Text("Buscar zona"),
        content=ft.Column([
            ft.Row([place_input]),
            place_results, search_credit,
        ], width=365, tight=True),
        actions=[ft.TextButton(tr("Cerrar", "Close"), on_click=close_search)],
    )

    def open_search(_):
        nonlocal search_token
        if drawing:
            notify("Cierra o cancela el dibujo antes de buscar otro lugar.", "#775019")
            return
        search_token = str(uuid4())
        place_input.value = ""
        using_google = active_provider == "google" and google_search_enabled()
        place_input.hint_text = "Busca una dirección o un lugar" if using_google else "Buscar ciudad o localidad"
        place_results.controls = []
        search_credit.value = "Google Maps" if using_google else "Open-Meteo · GeoNames"
        page.show_dialog(search_dialog)

    map_stack.controls.insert(-1, ft.Container(right=14, top=14, content=ft.Row([
        *([] if page.web else [ft.IconButton(
            ft.Icons.EDIT_LOCATION_ALT_OUTLINED, tooltip="Dibujar parcela", on_click=draw_parcel,
            bgcolor="#E8F6FF", icon_color="#123250",
        )]),
        ft.Button(tr("Buscar", "Search"), icon=ft.Icons.SEARCH, on_click=open_search,
                  style=ft.ButtonStyle(bgcolor="#E8F6FF", color="#123250")),
    ], spacing=6)))
    reopen_analysis = ft.IconButton(ft.Icons.ANALYTICS_OUTLINED, tooltip="Abrir análisis",
                                    on_click=open_drawer, icon_color="#DCF5E9")

    def explore_map(_):
        show_map()
        page.update()

    explore_button = ft.TextButton(tr("Mapa", "Map"), icon=ft.Icons.MAP_OUTLINED,
                                   url=map_url if page.web else None,
                                   on_click=None if page.web else explore_map,
                                   style=ft.ButtonStyle(color="#DCF5E9"))
    map_toolbar = ft.Row([
            ft.IconButton(ft.Icons.HOME_OUTLINED if page.web else ft.Icons.PUBLIC,
                          tooltip="Inicio" if page.web else "Volver al globo",
                          url=home_url if page.web else None,
                          on_click=None if page.web else return_to_globe,
                          icon_color="#DCF5E9"),
            *([] if page.web else [reopen_analysis]),
        ], spacing=0, visible=False)
    toolbar = ft.Container(bgcolor="#081b18", padding=ft.Padding.symmetric(horizontal=16, vertical=6), content=ft.Row([
            ft.Image(src="landing/logo.webp", width=30, height=30, border_radius=6, visible=not page.web),
            ft.Text("Parcela" if page.web else "TerraSprout", color="#FFFFFF", size=20, weight=ft.FontWeight.BOLD, expand=True,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            explore_button,
            map_toolbar,
        ], spacing=2))
    landing = fwv.WebView(url=project_url, expand=True, visible=False) if page.web else None
    if page.web:
        crops_url = origin._replace(path="/crops3d.html", query="", fragment="").geturl()
        crops_view = fwv.WebView(url=crops_url, expand=True, visible=False)
        header_view = fwv.WebView(url=f"{chrome_url}?vista=header&pagina=mapa&lang={lang}", height=73)
        map_page = root
        page.add(header_view, map_page, landing, crops_view)
        assistant.attach(landing, crops_view, header_view)
    else:
        page.add(toolbar, root)
    page.on_resize = resize
    resize()
    last_point_route = None

    async def open_point_route(route):
        nonlocal last_point_route
        if not route or route == last_point_route:
            return
        point = page.query.to_dict.get("punto")
        if not point:
            last_point_route = None
            return
        try:
            latitude, longitude = map(float, point.split(","))
        except ValueError:
            return
        if not (-85 <= latitude <= 85 and -180 <= longitude <= 180):
            return
        last_point_route = route
        await select(latitude, longitude, "Coordenadas de la parcela")

    if page.web:
        async def open_route(route):
            path = urlsplit(route or "").path.rstrip("/")
            params = page.query.to_dict
            crops_view.visible = path == "/cultivos"
            if crops_view.visible:
                assistant.button.visible = False
                crops_view.url = urlsplit(crops_url)._replace(
                    query=urlencode({key: params[key] for key in ("cultivo", "riego", "lang") if key in params}),
                ).geturl()
                landing.visible = header_view.visible = map_page.visible = False
                page.update()
                return
            show_landing = path not in {"/mapa", "/globo"} and not page.query.to_dict.get("punto")
            landing.visible = show_landing
            assistant.button.visible = not show_landing
            header_view.visible = map_page.visible = not show_landing
            section = page.query.to_dict.get("seccion")
            if show_landing and section in {"video", "proyecto", "equipo"}:
                landing.url = f"{project_url}#{section}"
            if path in {"/mapa", "/globo"}:
                show_map()
            page.update()
            if path == "/mapa" and page.query.to_dict.get("accion") == "ubicacion":
                page.run_task(locate)
            if path == "/mapa" and page.query.to_dict.get("accion") == "buscar":
                open_search(None)
            await open_point_route(route)

        async def route_changed(event):
            await open_route(event.route)

        page.on_route_change = route_changed
        await open_route(page.route)



if __name__ == "__main__":
    ft.run(main, assets_dir="assets", route_url_strategy=ft.RouteUrlStrategy.PATH)

"""Reusable crop and irrigation preview for Flet web views."""

from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import flet as ft
import flet_webview as fwv
from agricultural_assistant import WATER


SCENARIO_LABELS = {
    "es": {"rainfed": "Secano", "irrigated_gravity": "Gravedad", "irrigated_drip": "Goteo"},
    "en": {"rainfed": "Rainfed", "irrigated_gravity": "Gravity", "irrigated_drip": "Drip"},
}


class CropScene:
    def __init__(self, page_url, preferences, *, height=200, lang="es"):
        origin = urlsplit(page_url or "")
        scheme = {"ws": "http", "wss": "https"}.get(origin.scheme, origin.scheme)
        self.origin = origin._replace(scheme=scheme, path="/crops3d.html", fragment="")
        self.lang = lang
        self.height = height
        self._key = uuid4().hex
        self._preferences = preferences
        self._revision = 0
        self.control = ft.Container(height=height, visible=False, border_radius=12, clip_behavior=ft.ClipBehavior.ANTI_ALIAS)

    def url(self, crop, irrigation, mode="chat"):
        query = urlencode({
            "cultivo": crop, "riego": irrigation, "visor": mode, "lang": self.lang,
            "estado": self._key, "v": "riego-5",
        })
        return self.origin._replace(query=query).geturl()

    def show(self, crop, irrigation):
        self._revision += 1
        self.control.content = fwv.WebView(
            key=f"{self._key}-{self._revision}", url=self.url(crop, irrigation), expand=True,
        )
        self.control.visible = True

    def hide(self):
        self._revision += 1
        self.control.visible = False
        self.control.content = None

    async def switch(self, crop, irrigation):
        if self.control.content is None:
            self.show(crop, irrigation)
            return
        if not await self._preferences.set(f"terrasprout.crop-scene.{self._key}", irrigation):
            raise RuntimeError("The browser refused to store the 3D scene selection.")


def crop_scene_controls(page, crop, selected, scores, *, preferences, height=200, lang="es", before_update=None):
    """Return external scenario buttons and a viewer driven by the selection."""
    scene = CropScene(page.url, preferences, height=height, lang=lang)
    labels = SCENARIO_LABELS.get(lang, SCENARIO_LABELS["es"])
    buttons = {}
    show_text, hide_text = ("View 3D", "Hide 3D") if lang == "en" else ("Ver 3D", "Ocultar 3D")

    def refresh():
        for scenario, button in buttons.items():
            button.style = ft.ButtonStyle(bgcolor="#C5E4D3" if scenario == selected else None)
        toggle.content = hide_text if scene.control.visible else show_text
        if before_update:
            before_update()
        page.update()

    def choose(scenario):
        async def on_click(_):
            nonlocal selected
            if selected != scenario or not scene.control.visible:
                selected = scenario
                try:
                    await scene.switch(crop, WATER[scenario][1])
                except (RuntimeError, OSError):
                    if selected == scenario:
                        scene.show(crop, WATER[scenario][1])
            refresh()
        return on_click

    def toggle_view(_):
        if scene.control.visible:
            scene.hide()
        else:
            scene.show(crop, WATER[selected][1])
        refresh()

    for scenario, score in sorted(scores.items(), key=lambda pair: -pair[1]):
        if scenario not in labels:
            continue
        buttons[scenario] = ft.TextButton(
            f"{labels[scenario]} · {score:g}/100", on_click=choose(scenario),
            style=ft.ButtonStyle(bgcolor="#C5E4D3" if scenario == selected else None),
        )
    toggle = ft.TextButton(show_text, icon=ft.Icons.VIEW_IN_AR_OUTLINED, on_click=toggle_view)
    return [ft.Row([*buttons.values(), toggle], wrap=True, spacing=3, run_spacing=3), scene.control]

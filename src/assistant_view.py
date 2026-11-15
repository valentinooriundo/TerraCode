"""Reusable Flet entry point for the agricultural assistant."""

from time import monotonic
from urllib.parse import urlencode

import flet as ft

from agricultural_assistant import AgriculturalAssistant, Parcel, WATER


class AssistantView:
    def __init__(self, page, *, embedded=False):
        self.page = page
        self.embedded = embedded
        self.service = AgriculturalAssistant()
        self.parcel = None
        self.messages = []
        self.busy = False
        self.last_sent = float("-inf")
        self._embedded_views = ()
        self._suspended_views = []
        self.context = ft.Text("Selecciona una parcela para recibir opciones locales.", size=13)
        self.history = ft.ListView(
            controls=[ft.Text("Hola. Pregúntame qué cultivos evaluar o cómo comparar los tipos de riego.")],
            spacing=12, auto_scroll=True, expand=True,
        )
        self.status = ft.Text(size=12)
        self.input = ft.TextField(
            label="Tu pregunta", expand=True, max_length=1000, on_submit=self._send,
        )
        self.send = ft.IconButton(ft.Icons.SEND_ROUNDED, tooltip="Enviar pregunta", on_click=self._send)
        header_actions = [ft.Container(width=44)] if embedded else [
            ft.IconButton(ft.Icons.CLOSE, tooltip="Cerrar asistente", on_click=self._close),
        ]
        parcel_action = {"url": ft.Url("/mapa", target=ft.UrlTarget.TOP)} if embedded else {
            "on_click": self._map,
        }
        self.body = ft.Column([
            ft.Row([
                ft.Image(src="terra-bot-reference.png", width=48, height=48),
                ft.Text("Asistente agrícola", size=20, weight=ft.FontWeight.BOLD, expand=True),
                *header_actions,
            ]),
            self.context,
            ft.TextButton("Elegir parcela en el mapa", icon=ft.Icons.MAP_OUTLINED, **parcel_action),
            self.history,
            self.status,
            ft.Row([self.input, self.send]),
            ft.Text("Las preguntas se envían a Gemini. Evita compartir datos personales.", size=11),
        ], spacing=8, expand=embedded)
        self.button = ft.Container(
            right=18, bottom=18, visible=False,
            content=ft.Semantics(
                label="Abrir asistente agrícola", button=True, on_tap=self.open,
                content=ft.GestureDetector(
                    mouse_cursor=ft.MouseCursor.CLICK,
                    on_tap=self.open,
                    content=ft.Image(src="terra-bot-reference.png", width=72, height=72),
                ),
            ),
        )
        self.dialog = ft.AlertDialog(
            modal=True, content=self.body, on_dismiss=self._dismissed,
            inset_padding=ft.Padding.symmetric(horizontal=12, vertical=12),
            content_padding=14, bgcolor="#EFF4EF", barrier_color="#66082118",
        )

    def mount_embedded(self):
        self.page.add(ft.Container(content=self.body, expand=True, padding=16))

    def attach(self, *embedded_views):
        """Register browser frames that can intercept input above a Flet dialog."""
        self._embedded_views = embedded_views
        self.page.overlay.append(self.button)

    def set_parcel(self, latitude, longitude, label):
        self.parcel = Parcel(latitude, longitude, label)
        self.context.value = f"Parcela: {label} · {latitude:.4f}, {longitude:.4f}"

    def open(self, _=None):
        if self.dialog.open:
            return
        self.body.width = max(180, min(520, (self.page.width or 450) - 54))
        self.body.height = max(180, min(520, (self.page.height or 700) - 58))
        self._suspended_views = [view for view in self._embedded_views if view.visible]
        for view in self._suspended_views:
            view.visible = False
        if self._suspended_views:
            self.page.update()
        self.page.show_dialog(self.dialog)

    def _dismissed(self, _=None):
        if self.dialog.open or not self._suspended_views:
            return
        for view in self._suspended_views:
            view.visible = True
        self._suspended_views.clear()
        self.page.update()

    def _close(self, _):
        self.page.pop_dialog()
        self._dismissed()

    async def _map(self, _):
        self._close(None)
        await self.page.push_route("/mapa")

    def _option(self, candidate, reason):
        water, mode = WATER[candidate.scenario]
        query = urlencode({"cultivo": candidate.code, "riego": mode})
        route = f"/cultivos?{query}"

        async def open_gallery(_):
            self._close(None)
            await self.page.push_route(route)

        action = {"url": ft.Url(route, target=ft.UrlTarget.TOP)} if self.embedded else {
            "on_click": open_gallery,
        }
        return ft.Container(
            padding=10, border_radius=10, bgcolor="#E4F1E9",
            content=ft.Column([
                ft.Text(f"{candidate.crop} · {water}", weight=ft.FontWeight.BOLD),
                ft.Text(f"Aptitud estimada: {candidate.score:g} · Histórico: {candidate.period}", size=12),
                ft.Text(reason),
                ft.TextButton("Ver en 3D", **action),
            ], spacing=5),
        )

    def _add(self, controls):
        self.history.controls.append(ft.Column(controls, spacing=6))
        del self.history.controls[:-24]

    async def _send(self, _):
        message = (self.input.value or "").strip()[:1000]
        if not message or self.busy:
            return
        if monotonic() - self.last_sent < 2:
            self.status.value = "Espera un momento antes de enviar otra pregunta."
            self.page.update()
            return
        self.busy = True
        self.last_sent = monotonic()
        self.input.value = ""
        self.input.disabled = self.send.disabled = True
        self.status.value = "Consultando…"
        self._add([ft.Text(message, weight=ft.FontWeight.W_600, selectable=True)])
        self.page.update()
        try:
            self.messages.append(("user", message))
            result = await self.service.reply(self.messages, self.parcel)
            self.messages.append(("model", "\n".join(filter(None, (result.answer, result.question)))))
            del self.messages[:-8]
            controls = [ft.Text(result.answer, selectable=True)]
            controls.extend(self._option(candidate, reason) for candidate, reason in result.options)
            if result.question:
                controls.append(ft.Text(result.question, weight=ft.FontWeight.W_600))
            self._add(controls)
            self.status.value = ""
        finally:
            self.busy = False
            self.input.disabled = self.send.disabled = False
            self.page.update()

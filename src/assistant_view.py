"""Reusable Flet entry point for the agricultural assistant."""

import asyncio
import json
from dataclasses import asdict
from time import monotonic
from urllib.parse import urlencode
from uuid import uuid4

import flet as ft
from agricultural_assistant import AgriculturalAssistant, Candidate, Parcel, WATER
from crop_scene import crop_scene_controls


HISTORY_KEY = "terrasprout.assistant.history.v1"
NASA_POWER_DOCS = "https://power.larc.nasa.gov/docs/services/api/temporal/monthly/"
WATER_EXAMPLE = "Tengo agua de canal de diciembre a marzo y riego por gravedad. El resto del año dependo de la lluvia."
WATER_EN = {
    "rainfed": ("Rainfed", "The plot relies on rainfall."),
    "irrigated_gravity": ("Gravity", "Water flows through furrows."),
    "irrigated_drip": ("Drip", "Pipes deliver water close to each plant."),
}


class AssistantView:
    def __init__(self, page, *, embedded=False, full_page=False, lang="es"):
        self.page = page
        self.embedded = embedded
        self.full_page = full_page
        self.lang = lang
        tr = self._tr
        self.service = AgriculturalAssistant(lang)
        self.parcel = None
        self.preferences = ft.SharedPreferences()
        self.threads = {}
        self.active_id = uuid4().hex
        self.threads[self.active_id] = []
        self.busy = False
        self.last_sent = float("-inf")
        self._embedded_views = ()
        self._suspended_views = []
        self.context = ft.Text(tr("Selecciona una parcela para recibir opciones locales.", "Select a plot for local recommendations."), size=13)
        self.history = ft.ListView(
            controls=[],
            spacing=12, auto_scroll=True, expand=True,
        )
        self.status = ft.Text(size=12)
        self.thread_picker = ft.PopupMenuButton(
            icon=ft.Icons.HISTORY, tooltip=tr("Historial de chats", "Chat history"),
        )
        self.new_chat = ft.IconButton(ft.Icons.ADD_COMMENT_OUTLINED, tooltip=tr("Nuevo chat", "New chat"), on_click=self._new_chat)
        self.input = ft.TextField(
            label=tr("Tu pregunta", "Your question"), expand=True, max_length=1000, on_submit=self._send,
        )
        self.send = ft.IconButton(ft.Icons.SEND_ROUNDED, tooltip="Enviar pregunta", on_click=self._send)
        self.expand_chat = ft.IconButton(
            ft.Icons.OPEN_IN_FULL, tooltip=tr("Abrir chat en grande", "Open full chat"),
            url=ft.Url(f"/asistente?lang={lang}", target=ft.UrlTarget.TOP),
        )
        header_actions = [self.thread_picker, self.new_chat]
        if full_page:
            header_actions.append(ft.IconButton(ft.Icons.HOME_OUTLINED, tooltip=tr("Volver a Inicio", "Back to home"), url=f"/?lang={lang}"))
        else:
            header_actions.append(self.expand_chat)
            header_actions.append(ft.Container(width=40) if embedded else
                                  ft.IconButton(ft.Icons.CLOSE, tooltip="Cerrar asistente", on_click=self._close))
        parcel_action = {"url": ft.Url(f"/mapa?lang={lang}", target=ft.UrlTarget.TOP)} if embedded else {
            "on_click": self._map,
        }
        self.parcel_button = ft.TextButton(tr("Elegir parcela en el mapa", "Choose a plot on the map"), icon=ft.Icons.MAP_OUTLINED, **parcel_action)
        self.body = ft.Column([
            ft.Row([
                ft.Image(src="terra-bot-reference.png", width=48, height=48),
                ft.Text(tr("Asistente agrícola", "Farm assistant"), size=17, weight=ft.FontWeight.BOLD, expand=True),
                *header_actions,
            ]),
            ft.Row([self.context, self.parcel_button], wrap=True, spacing=6),
            self.history,
            self.status,
            ft.Row([self.input, self.send]),
            ft.Text(tr("Se guarda el historial en este navegador. Las preguntas se envían a Gemini.",
                       "Chat history stays in this browser. Questions are sent to Gemini."), size=11),
        ], spacing=8, expand=embedded)
        if full_page:
            self.body.width = 760
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
        self._render_thread()

    def _tr(self, es, en):
        return en if self.lang == "en" else es

    async def mount_embedded(self):
        self.page.services.append(self.preferences)
        self.input.disabled = self.send.disabled = self.thread_picker.disabled = self.new_chat.disabled = True
        self.page.add(ft.Container(
            content=self.body, expand=True, padding=16,
            alignment=ft.Alignment.TOP_CENTER if self.full_page else None,
        ))
        await self._load()
        self.input.disabled = self.send.disabled = self.thread_picker.disabled = self.new_chat.disabled = False
        self.page.update()

    def attach(self, *embedded_views):
        """Register browser frames that can intercept input above a Flet dialog."""
        self._embedded_views = embedded_views
        self.page.services.append(self.preferences)
        self.page.overlay.append(self.button)

    def set_parcel(self, latitude, longitude, label):
        self.parcel = Parcel(latitude, longitude, label)
        self.context.value = f"{self._tr('Parcela', 'Plot')}: {label} · {latitude:.4f}, {longitude:.4f}"
        self.parcel_button.content = self._tr("Volver a elegir parcela", "Change plot")
        self.expand_chat.url = ft.Url("/asistente?" + urlencode({
            "punto": f"{latitude:.5f},{longitude:.5f}", "zona": label, "lang": self.lang,
        }), target=ft.UrlTarget.TOP)

    async def open(self, _=None):
        if self.dialog.open:
            return
        if not self.busy:
            await self._load()
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
        await self.page.push_route("/mapa", lang=self.lang)

    async def _load(self):
        try:
            saved = json.loads(await self.preferences.get(HISTORY_KEY) or "{}")
            threads = saved.get("threads")
            active = saved.get("active")
            if isinstance(threads, dict) and active in threads:
                self.threads, self.active_id = threads, active
                self._render_thread()
        except (TypeError, ValueError, KeyError, AttributeError, RuntimeError, TimeoutError):
            pass

    async def _save(self):
        try:
            value = json.dumps({"active": self.active_id, "threads": self.threads}, ensure_ascii=False)
            await self.preferences.set(HISTORY_KEY, value)
        except (TypeError, ValueError, RuntimeError, TimeoutError):
            self.status.value = "El navegador no pudo guardar el historial."

    def _render_thread(self):
        self.thread_picker.items = [
            ft.PopupMenuItem(
                content=ft.Text(self._thread_title(entries)),
                icon=ft.Icons.CHECK if key == self.active_id else ft.Icons.CHAT_BUBBLE_OUTLINE,
                data=key, on_click=self._select_thread,
            )
            for key, entries in reversed(list(self.threads.items()))
        ]
        self.history.controls.clear()
        entries = self.threads[self.active_id]
        self._add("model", [ft.Text(self._tr(
            "¡Hola! ¿En qué puedo ayudarte hoy? Puedo ayudarte a evaluar qué sembrar, comparar tipos de riego y entender el clima de tu parcela.",
            "Hi! How can I help today? We can explore what to plant, compare irrigation options, or look at your plot’s climate.",
        ))])
        for entry in entries:
            self._show_entry(entry)

    def _thread_title(self, entries):
        first = next((entry["text"] for entry in entries if entry["role"] == "user"), "")
        return (first[:34] + ("…" if len(first) > 34 else "")) or self._tr("Chat nuevo", "New chat")

    async def _select_thread(self, event):
        key = event.control.data
        if self.busy or key not in self.threads:
            return
        self.active_id = key
        self.input.value = ""
        self.status.value = ""
        self._render_thread()
        self.page.update()
        await self._save()

    async def _new_chat(self, _):
        if self.busy:
            return
        if not self.threads[self.active_id]:
            self.input.value = ""
            self.page.update()
            return
        self.active_id = uuid4().hex
        self.threads[self.active_id] = []
        while len(self.threads) > 15:
            del self.threads[next(iter(self.threads))]
        self.input.value = ""
        self.status.value = ""
        self._render_thread()
        self.page.update()
        await self._save()

    def _option(self, candidate, reason):
        tr = self._tr
        water = tr(WATER[candidate.scenario][0], WATER_EN[candidate.scenario][0])
        scores = candidate.scenario_scores or {candidate.scenario: candidate.score}
        viewer = crop_scene_controls(
            self.page, candidate.code, candidate.scenario, scores,
            preferences=self.preferences, height=300 if self.full_page else 210, lang=self.lang,
            before_update=lambda: setattr(self.history, "auto_scroll", False),
        )
        return ft.Container(
            padding=10, border_radius=10, bgcolor="#E4F1E9",
            content=ft.Column([
                ft.Text(f"{candidate.crop} · {water}", weight=ft.FontWeight.BOLD),
                ft.Text(f"{tr('Escenarios evaluados', 'Scenarios evaluated')} · {candidate.period}", size=12),
                ft.Text(reason),
                *viewer,
            ], spacing=5),
        )

    def _add(self, role, controls):
        is_user = role == "user"
        bubble = ft.Container(
            bgcolor="#D4EADB" if is_user else "#FFFFFF", padding=10, border_radius=12,
            content=ft.Column([
                ft.Text(self._tr("Tú", "You") if is_user else "TerraSprout", size=12, weight=ft.FontWeight.BOLD),
                *controls,
            ], spacing=5),
        )
        self.history.controls.append(ft.Container(
            margin=ft.Margin.only(left=34 if is_user else 0, right=0 if is_user else 34),
            content=bubble,
        ))

    def _show_entry(self, entry):
        tr = self._tr
        controls = [ft.Text(entry["text"], selectable=True)]
        options = entry.get("options", [])
        if options:
            controls.extend([
                ft.Text(tr("Histórico climático de NASA POWER · Aptitud estimada por TerraSprout",
                           "NASA POWER climate history · Suitability estimated by TerraSprout"), size=12),
                ft.TextButton(tr("Ver fuente NASA POWER", "View NASA POWER source"), url=ft.Url(NASA_POWER_DOCS, target=ft.UrlTarget.BLANK)),
            ])
            controls.extend(self._option(Candidate(**candidate), reason) for candidate, reason in options)
        if entry.get("question"):
            controls.append(ft.Text(entry["question"], weight=ft.FontWeight.W_600))
            if any(word in entry["question"].lower() for word in ("agua", "riego", "water", "irrigation")):
                controls.extend([
                    ft.Text(tr("Indica la fuente de agua, los meses disponibles y el sistema de riego.",
                               "Tell us the water source, months available, and irrigation system."), size=12),
                    ft.Text(f"{tr('Ejemplo', 'Example')}: {self._water_example()}", size=12),
                    ft.TextButton(tr("Usar ejemplo", "Use example"), on_click=self._use_example),
                ])
        self._add(entry["role"], controls)

    def _use_example(self, _):
        if not self.busy and not (self.input.value or "").strip():
            self.input.value = self._water_example()
            self.page.update()

    def _water_example(self):
        return self._tr(WATER_EXAMPLE, "I have canal water from December to March and use gravity irrigation. I rely on rain the rest of the year.")

    async def _animate_typing(self):
        index = 0
        while True:
            self.status.value = self._tr("TerraSprout está escribiendo", "TerraSprout is typing") + "." * (index % 3 + 1)
            self.page.update()
            index += 1
            await asyncio.sleep(.4)

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
        self.history.auto_scroll = True
        self.input.disabled = self.send.disabled = self.thread_picker.disabled = self.new_chat.disabled = True
        entries = self.threads[self.active_id]
        entries.append({"role": "user", "text": message})
        self._render_thread()
        self.page.update()
        animation = asyncio.create_task(self._animate_typing())
        try:
            messages = [(entry["role"], "\n".join(filter(None, (entry["text"], entry.get("question")))))
                        for entry in entries[-9:]]
            result = await self.service.reply(messages, self.parcel)
            entries.append({
                "role": "model", "text": result.answer, "question": result.question,
                "options": [(asdict(candidate), reason) for candidate, reason in result.options],
            })
            del entries[:-40]
            self._render_thread()
        finally:
            animation.cancel()
            self.status.value = ""
            self.busy = False
            self.input.disabled = self.send.disabled = self.thread_picker.disabled = self.new_chat.disabled = False
            self.page.update()
            await self._save()
            self.page.update()

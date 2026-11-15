"""Reusable Flet globe. Its gestures never trigger navigation or GPS."""

from math import asin, atan2, degrees, exp, radians, sin, cos, sqrt

import flet as ft


def globe_point(x, y, heading, latitude=8):
    """Invert the orthographic projection used to generate the Earth frames."""
    radius_squared = x * x + y * y
    if radius_squared > 1:
        return None
    z = sqrt(1 - radius_squared)
    tilt = radians(latitude)
    lat = degrees(asin(max(-1, min(1, y * cos(tilt) + z * sin(tilt)))))
    lon = heading + degrees(atan2(x, z * cos(tilt) - y * sin(tilt)))
    return lat, (lon + 180) % 360 - 180


class GlobeView(ft.Container):
    def __init__(self, on_point=None):
        super().__init__(alignment=ft.Alignment.CENTER, clip_behavior=ft.ClipBehavior.HARD_EDGE)
        self._angle = -75.0
        self._zoom = .82
        self._diameter = 384
        self._pinch_origin = 1.0
        self._frame = -75
        self._tilt = 8.0
        self._frame_tilt = 8
        self._on_point = on_point
        self._image = ft.Image(
            src=f"earth-{self._frame}.webp", width=384, height=384, fit=ft.BoxFit.CONTAIN,
            gapless_playback=True, semantics_label="Globo terrestre NASA Blue Marble",
        )
        self.content = ft.Stack([
            ft.Container(
                left=0, right=0, top=0, bottom=0, alignment=ft.Alignment.CENTER,
                content=ft.GestureDetector(
                    content=self._image, mouse_cursor=ft.MouseCursor.GRAB,
                    on_scale_start=self._start, on_scale_update=self._gesture,
                    on_scroll=self._wheel, on_tap_up=self._pick, drag_interval=24,
                ),
            ),
            ft.Container(left=12, top=12, padding=8, bgcolor="#152940", border_radius=8,
                         content=ft.Text("Arrastra para girar · toca para explorar", color="#E5F3FF", size=12)),
            ft.Container(left=12, bottom=16, content=ft.Row([
                self._button(ft.Icons.REMOVE, "Alejar", lambda _: self._set_zoom(self._zoom / 1.25)),
                self._button(ft.Icons.ADD, "Acercar", lambda _: self._set_zoom(self._zoom * 1.25)),
                self._button(ft.Icons.RESTART_ALT, "Restablecer zoom", lambda _: self._set_zoom(.82)),
            ], spacing=4)),
        ], expand=True)

    @staticmethod
    def _button(icon, label, handler):
        return ft.IconButton(icon, tooltip=label, on_click=handler,
                             bgcolor="#152940", icon_color="#E5F3FF")

    def resize_globe(self, width, height):
        self._diameter = min(890, max(100, width * .96), max(100, height * .94))
        self._apply_size()

    def _apply_size(self):
        self._image.width = self._image.height = self._diameter * self._zoom

    def _set_zoom(self, zoom, update=True):
        self._zoom = min(1, max(.48, zoom))
        self._apply_size()
        if update:
            self._image.update()

    def _start(self, _):
        self._pinch_origin = self._zoom

    def _gesture(self, event):
        if event.pointer_count >= 2:
            self._set_zoom(self._pinch_origin * event.scale)
            return
        factor = 240 / (self._diameter * self._zoom)
        self._angle = (self._angle - event.focal_point_delta.x * factor + 180) % 360 - 180
        self._tilt = max(-90, min(90, self._tilt + event.focal_point_delta.y * factor))
        tilt = min((-90, -60, -30, 8, 30, 60, 90), key=lambda value: abs(value - self._tilt))
        step = 5 if tilt == 8 else 15
        frame = (round(self._angle / step) * step + 180) % 360 - 180
        if abs(tilt) == 90:
            frame = 0
        src = f"earth-{frame}.webp" if tilt == 8 else f"earth-v2-{tilt}-{frame}.webp"
        if src != self._image.src:
            self._frame = frame
            self._frame_tilt = tilt
            self._image.src = src
            self._image.update()

    async def _pick(self, event):
        half = self._image.width / 2
        point = globe_point(
            (event.local_position.x - half) / half,
            (half - event.local_position.y) / half,
            self._frame, self._frame_tilt,
        )
        if point and self._on_point:
            await self._on_point(*point)

    def _wheel(self, event):
        delta = min(200, max(-200, event.scroll_delta.y))
        self._set_zoom(self._zoom * exp(-delta / 600))

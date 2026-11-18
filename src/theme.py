"""Paleta de colores de TerraCode (equivalente a las variables CSS de diseño)."""

import flet as ft

# Marca y estructura
PRIMARY = "#1B4332"          # Verde Bosque Profundo
PRIMARY_HOVER = "#2D6A4F"    # Verde Hoja Vibrante
PRIMARY_LIGHT = "#ECFDF5"    # Verde Muy Claro
ACCENT = "#D97706"           # Ámbar Cosecha
ACCENT_DARK = "#B45309"      # Ámbar Oscuro

# Fondos
BG_MAIN = "#F8FAF9"          # Blanco Humo
BG_SURFACE = "#FFFFFF"       # Blanco Puro
BORDER_SUBTLE = "#E5E7EB"    # Gris Claro

# Tipografía
TEXT_MAIN = "#1F2937"        # Gris Pizarra Oscuro
TEXT_MUTED = "#6B7280"       # Gris Neutro
TEXT_ON_PRIMARY = "#FFFFFF"

# Estados del sistema
SUCCESS = "#16A34A"
WARNING = "#EAB308"
DANGER = "#DC2626"           # Rojo Terracota
INFO = "#0284C7"


def app_theme() -> ft.Theme:
    """Tema Material para que los controles (inputs, botones, etc.) usen la paleta."""
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=PRIMARY,
            on_primary=TEXT_ON_PRIMARY,
            primary_container=PRIMARY_LIGHT,
            on_primary_container=PRIMARY,
            secondary=PRIMARY_HOVER,
            on_secondary=TEXT_ON_PRIMARY,
            tertiary=ACCENT,
            on_tertiary=TEXT_ON_PRIMARY,
            error=DANGER,
            on_error=TEXT_ON_PRIMARY,
            surface=BG_SURFACE,
            on_surface=TEXT_MAIN,
            on_surface_variant=TEXT_MUTED,
            outline=BORDER_SUBTLE,
        ),
    )

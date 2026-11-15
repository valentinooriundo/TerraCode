"""Generate a print-ready summary of the selected TerraSprout plot."""

from io import BytesIO
from statistics import mean
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import nasa
from agricultural_assistant import WATER


INK = colors.HexColor("#15362A")
LIGHT = colors.HexColor("#EAF4ED")
GREEN = colors.HexColor("#21694E")
EN_METRICS = {
    "T2M": "Average air temperature", "T2M_MIN": "Minimum air temperature",
    "T2M_MAX": "Maximum air temperature", "RH2M": "Relative humidity",
    "ALLSKY_SFC_SW_DWN": "Solar radiation", "WS2M": "Wind at 2 m",
    "GWETTOP": "Surface soil moisture", "GWETROOT": "Root-zone soil moisture",
    "GWETPROF": "Profile soil moisture",
}


def parcel_pdf(report, lang="es"):
    def tr(es, en):
        return en if lang == "en" else es

    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=A4, leftMargin=42, rightMargin=42,
                            topMargin=44, bottomMargin=48, title="TerraSprout | " + tr("Ficha técnica", "Plot factsheet"))
    base = getSampleStyleSheet()
    title = ParagraphStyle("PlotTitle", parent=base["Title"], fontSize=27, leading=31,
                           textColor=INK, alignment=0, spaceAfter=12)
    heading = ParagraphStyle("PlotSection", parent=base["Heading2"], textColor=GREEN, spaceBefore=14, spaceAfter=7)
    body = ParagraphStyle("PlotBody", parent=base["BodyText"], textColor=INK, fontSize=9.5, leading=13)
    numeric = ParagraphStyle("PlotValue", parent=body, alignment=TA_RIGHT)
    th = ParagraphStyle("PlotTableHeader", parent=body, fontName="Helvetica-Bold", textColor=colors.white)
    story = []

    def paragraph(text, style=body):
        return Paragraph(escape(str(text)), style)

    def table(headers, rows, widths):
        cells = [[paragraph(label, th) for label in headers]]
        cells.extend([[paragraph(value, body if i == 0 else numeric) for i, value in enumerate(row)] for row in rows])
        grid = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
        grid.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GREEN),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT, colors.white]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story.append(grid)

    def section(es, en):
        story.append(paragraph(tr(es, en), heading))

    missing = tr("Sin datos", "No data")
    story.extend([
        paragraph("TERRASPROUT  /  " + tr("ANÁLISIS DE PARCELA", "PLOT ANALYSIS"), heading),
        paragraph(tr("Ficha técnica de la parcela", "Plot factsheet"), title),
        paragraph(report["name"]),
        paragraph(f"{report['latitude']:.5f}, {report['longitude']:.5f}"),
        paragraph(f"{tr('Período consultado', 'Selected period')}: {report['start']} / {report['end']}"),
    ])
    section("Clima", "Climate")
    climate = report.get("climate")
    if climate:
        rows = []
        for code, label in nasa.METRICS.items():
            series = [value for _, value in nasa.daily(climate, code) if value is not None]
            unit = climate.get("parameters", {}).get(code, {}).get("units", "").replace("m^2", "m²")
            value = missing
            if code == "PRECTOTCORR":
                label = tr("Lluvia acumulada", "Total rainfall")
                if series:
                    value = f"{sum(series):.2f} mm"
            else:
                label = tr(label, EN_METRICS.get(code, label))
                aggregate = {"T2M_MIN": min, "T2M_MAX": max}.get(code, mean)
                if series:
                    value = f"{aggregate(series):.2f} {unit}".strip()
            rows.append((label, value))
        rain = nasa.daily(climate, "PRECTOTCORR")
        dry = f"{nasa.dry_spell(rain)} {tr('días', 'days')}" if any(v is not None for _, v in rain) else missing
        rows.append((tr("Racha seca (< 1 mm/día)", "Dry spell (< 1 mm/day)"), dry))
        table([tr("Indicador", "Indicator"), tr("Resultado", "Result")], rows, [doc.width*.7, doc.width*.3])
    else:
        story.append(paragraph(missing))

    section("Humedad del suelo", "Soil moisture")
    soil = report.get("soil")
    if soil:
        rows = []
        for code, label in nasa.SOIL_METRICS.items():
            values = [v for _, v in nasa.daily(soil, code) if v is not None and 0 <= v <= 1]
            rows.append((tr(label, EN_METRICS.get(code, label)), f"{mean(values):.2f} / 1" if values else missing))
        table([tr("Indicador", "Indicator"), tr("Resultado", "Result")], rows, [doc.width*.7, doc.width*.3])
    else:
        story.append(paragraph(missing))
    story.extend([Spacer(1, 10), paragraph(tr(
        "Fuente de clima y suelo: NASA POWER. Los datos son regionales y no sustituyen mediciones de campo.",
        "Climate and soil source: NASA POWER. These regional data do not replace field measurements.",
    ))])

    story.append(PageBreak())
    section("Cultivos y escenarios de riego", "Crops and irrigation scenarios")
    crops = report.get("crops", {})
    names = {}
    scores = {}
    for scenario in WATER:
        for item in crops.get(scenario, {}).get("recommendations", []):
            names[item["code"]] = item["crop"]
            scores.setdefault(item["code"], {})[scenario] = item["score"]
    rows = []
    for code in sorted(scores, key=lambda key: (-max(scores[key].values()), names[key])):
        if not any(value > 0 for value in scores[code].values()):
            continue
        rows.append((names[code], *[
            f"{scores[code][scenario]:.2f}" if scores[code].get(scenario, 0) > 0 else "-"
            for scenario in WATER
        ]))
    if rows:
        period = next((data.get("reference_period") for data in crops.values() if data.get("reference_period")), "")
        story.append(paragraph(tr(
            f"Aptitud estimada por TerraSprout (/100) con histórico NASA POWER {period}. Un guion indica que no hay puntuación positiva para ese escenario.",
            f"TerraSprout suitability estimate (/100), using NASA POWER history {period}. A dash means no positive score for that scenario.",
        )))
        story.append(Spacer(1, 7))
        table([tr("Cultivo", "Crop"), tr("Secano", "Rainfed"), tr("Gravedad", "Gravity"), tr("Goteo", "Drip")],
              rows, [doc.width*.43, doc.width*.19, doc.width*.19, doc.width*.19])
    else:
        story.append(paragraph(tr("No hay cultivos con puntuación positiva disponible.", "No crops with positive scores are available.")))

    avocado = [(WATER[scenario][0] if lang == "es" else {"irrigated_gravity": "Gravity", "irrigated_drip": "Drip"}.get(scenario, scenario),
                data["avocado_gaez_v5"])
               for scenario, data in crops.items() if data.get("avocado_gaez_v5") is not None]
    if avocado:
        story.append(Spacer(1, 7))
        story.append(paragraph(tr("Palta (FAO GAEZ v5, 2001-2020): ", "Avocado (FAO GAEZ v5, 2001-2020): ") +
                               "; ".join(f"{name} {score:.2f}/100" for name, score in avocado)))

    section("Rotaciones", "Rotations")
    rotation = report.get("rotation") or {}
    if rotation.get("plans"):
        scenario = rotation.get("water_supply")
        label = WATER.get(scenario, ("", ""))[0]
        if lang == "en":
            label = {"rainfed": "Rainfed", "irrigated_gravity": "Gravity", "irrigated_drip": "Drip"}.get(scenario, "")
        previous = rotation.get("previous_crop")
        story.append(paragraph(f"{tr('Escenario', 'Scenario')}: {label}  |  {tr('Cultivo anterior', 'Previous crop')}: {names.get(previous, previous)}"))
        table([tr("Secuencia propuesta", "Suggested sequence"), tr("Aptitud mínima", "Minimum suitability")],
              [(" > ".join(plan["crops"]), f"{plan['minimum_suitability']:.2f}/100") for plan in rotation["plans"]],
              [doc.width*.73, doc.width*.27])
    else:
        story.append(paragraph(tr("No hay una secuencia sugerida para la configuración de rotación actual.",
                                   "No sequence is suggested for the current rotation settings.")))
    story.extend([Spacer(1, 10), paragraph(tr(
        "Ficha orientativa. La aptitud histórica no garantiza la cosecha ni confirma disponibilidad de agua.",
        "For planning only. Historical suitability does not guarantee a harvest or confirm water availability.",
    ))])

    def footer(canvas, document):
        canvas.setStrokeColor(LIGHT)
        canvas.line(42, 35, A4[0] - 42, 35)
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(42, 23, "TerraSprout  /  " + tr("Ficha de parcela", "Plot factsheet"))
        canvas.drawRightString(A4[0] - 42, 23, str(document.page))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()

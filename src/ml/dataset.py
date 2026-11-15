from pathlib import Path

import httpx
import rasterio

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "raw" / "gaez"

BASE_URL = (
    "https://gaez-v4-data.fao.org/data/"
    "res05/CRUTS32/Hist/8110H"
)

CROPS = {
    "mze": "Maíz",
    "phb": "Frijol",
    "wpo": "Papa",
}

def download_gaez():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for code, crop in CROPS.items():
        filename = f"sxHr_{code}.tif"
        destination = DATA_DIR / filename

        if destination.exists():
            print(f"{crop}: archivo existente")
            continue

        url = f"{BASE_URL}/{filename}"

        print(f"Descargando datos de {crop}...")

        try:
            response = httpx.get(
                url,
                timeout=60,
                follow_redirects=True,
            )

            response.raise_for_status()

            with rasterio.MemoryFile(response.content) as memory:
                with memory.open() as raster:
                    print(
                        f"Raster válido: "
                        f"{raster.width} × {raster.height}"
                    )

            destination.write_bytes(response.content)

            print(f"{crop}: descarga completada")

        except Exception as error:
            print(f"Error en {crop}: {error}")

if __name__ == "__main__":
    download_gaez()

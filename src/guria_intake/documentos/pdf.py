"""HTML → PDF con el Chrome/Chromium headless del servidor. Sin dependencias de Python."""

import glob
import os
import shutil
import subprocess
from pathlib import Path


def chromium() -> str | None:
    if os.environ.get("CHROMIUM_BIN"):
        return os.environ["CHROMIUM_BIN"]
    for nombre in ("chromium", "chromium-browser", "google-chrome"):
        if ruta := shutil.which(nombre):
            return ruta
    # Playwright instalado en el usuario (desarrollo)
    hallados = sorted(glob.glob(os.path.expanduser(
        "~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell")))
    return hallados[-1] if hallados else None


def a_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Imprime el HTML a PDF. False si no hay Chromium: el HTML igual sirve de adjunto."""
    binario = chromium()
    if not binario:
        return False
    subprocess.run(
        [binario, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
         "--virtual-time-budget=15000",  # tiempo para que carguen las fuentes
         f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()],
        check=True, capture_output=True, timeout=90,
    )
    return pdf_path.exists()


def guardar(html: str, carpeta: Path, nombre: str) -> Path:
    """Guarda nombre.html y lo pasa a nombre.pdf. Devuelve el PDF, o el HTML si no hubo Chromium."""
    ruta, pdf = carpeta / f"{nombre}.html", carpeta / f"{nombre}.pdf"
    ruta.write_text(html)
    return pdf if a_pdf(ruta, pdf) else ruta

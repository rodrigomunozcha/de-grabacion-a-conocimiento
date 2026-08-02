"""
Dibuja el mapa conceptual de la clase como una imagen de verdad.

Por que existe. La nota traia una seccion "mapa visual" que DESCRIBIA el mapa
en palabras: "en el centro iria X, del que salen tres ramas...". Describir un
dibujo no es un dibujo. El estudiante tenia que armarlo mentalmente, que es
justo el trabajo que un mapa deberia ahorrarle.

Como se logra sin motor de grafos. Un mapa conceptual de una clase no es un
grafo cualquiera: es un concepto central con ramas, y cada rama con un par de
puntos. Con esa forma fija el acomodo se calcula con trigonometria simple y no
hace falta graphviz ni instalar nada. A cambio, el modelo tiene que entregar la
estructura como datos y no como prosa (ver SKILL.md).

Si algo falla al dibujar, no se dibuja y listo. Un mapa es un extra: nunca
puede costarle el documento a una clase.
"""
import math
import tempfile
from pathlib import Path

COLOR_CENTRO = "#1F4E5F"
COLOR_RAMA = "#2E7486"
COLOR_HOJA = "#7BA7B5"
COLOR_TEXTO_CLARO = "#FFFFFF"
COLOR_TEXTO_OSCURO = "#1A1A1A"

_carpeta_temporal: Path | None = None


def _carpeta() -> Path:
    global _carpeta_temporal
    if _carpeta_temporal is None:
        _carpeta_temporal = Path(tempfile.mkdtemp(prefix="mapa_"))
    return _carpeta_temporal


def limpiar_temporales() -> None:
    global _carpeta_temporal
    if _carpeta_temporal is not None:
        import shutil
        shutil.rmtree(_carpeta_temporal, ignore_errors=True)
        _carpeta_temporal = None


def _envolver(texto: str, ancho: int) -> str:
    """Corta el texto en varias lineas para que quepa en su caja."""
    palabras, lineas, actual = texto.split(), [], ""
    for palabra in palabras:
        if len(actual) + len(palabra) + 1 <= ancho:
            actual = f"{actual} {palabra}".strip()
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return "\n".join(lineas)


def dibujar(centro: str, ramas: list[dict]) -> Path | None:
    """
    `ramas` es una lista de {"titulo": str, "puntos": [str, ...]}.

    Devuelve la ruta de la imagen, o None si no se pudo dibujar.
    """
    if not centro or not ramas:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch

        n = len(ramas)
        fig, ax = plt.subplots(figsize=(11, 8))
        ax.set_xlim(-10, 10)
        ax.set_ylim(-8, 8)
        ax.axis("off")

        def caja(x, y, texto, color, color_texto, tamano, ancho_texto, peso="normal"):
            etiqueta = _envolver(texto, ancho_texto)
            t = ax.text(x, y, etiqueta, ha="center", va="center", fontsize=tamano,
                        color=color_texto, weight=peso, zorder=3, linespacing=1.4)
            t.set_bbox(dict(boxstyle="round,pad=0.5", facecolor=color,
                            edgecolor="none", alpha=1.0))
            return t

        # Las ramas se reparten en circulo. Empezar arriba y avanzar en el
        # sentido del reloj hace que se lea como se leeria un reloj.
        radio = 6.0
        for i, rama in enumerate(ramas):
            angulo = math.pi / 2 - (2 * math.pi * i / n)
            rx, ry = radio * math.cos(angulo), radio * math.sin(angulo) * 0.72

            ax.plot([0, rx], [0, ry], color=COLOR_RAMA, linewidth=2, zorder=1, alpha=0.55)
            caja(rx, ry, rama.get("titulo", ""), COLOR_RAMA, COLOR_TEXTO_CLARO, 11, 22, "bold")

            puntos = (rama.get("puntos") or [])[:3]
            for j, punto in enumerate(puntos):
                # Los hijos se abren en abanico hacia afuera de su rama.
                desvio = (j - (len(puntos) - 1) / 2) * 0.42
                a = angulo + desvio
                px, py = (radio + 3.1) * math.cos(a), (radio + 3.1) * math.sin(a) * 0.72
                ax.plot([rx, px], [ry, py], color=COLOR_HOJA, linewidth=1.2,
                        zorder=1, alpha=0.6)
                caja(px, py, punto, "#EAF3F7", COLOR_TEXTO_OSCURO, 9, 20)

        caja(0, 0, centro, COLOR_CENTRO, COLOR_TEXTO_CLARO, 13, 20, "bold")

        destino = _carpeta() / "mapa.png"
        fig.savefig(destino, dpi=190, bbox_inches="tight", pad_inches=0.25,
                    facecolor="white")
        plt.close(fig)
        return destino
    except Exception:
        return None

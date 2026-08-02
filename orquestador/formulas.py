"""
Renderiza formulas matematicas para el .docx.

Dos caminos, segun donde va la formula:

- **Formula destacada** (sola en su linea, entre `$$`): se dibuja como imagen
  con matplotlib y se inserta centrada. Queda con tipografia matematica de
  verdad: barra de fraccion, radical que se estira sobre lo que cubre,
  sombrero sobre la p, subindices bien puestos.
- **Formula corta dentro de una frase** (entre `$`): se escribe como texto con
  subindices y superindices reales. Una imagen ahi quedaria desalineada con el
  renglon y con un tamano que no acompana al texto.

Por que no ecuaciones nativas de Word. Word usa OMML, un XML propio que
python-docx no sabe generar: habria que armarlo a mano por cada formula, es
fragil, y una mal formada deja el .docx sin abrir. La imagen se ve igual de
bien y no puede romper el documento.

Por que no cuesta tokens. El modelo escribe la formula en LaTeX, que es lo que
ya escribiria de todos modos. El dibujo lo hace matplotlib aca, en el Mac.

Si matplotlib no esta o falla, se cae solo al modo texto. Una formula fea es
mucho mejor que una clase sin documento.
"""
import re
import tempfile
from pathlib import Path

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

MARCA_DESTACADA = "$$"

# Un token es: _{...}, ^{...}, _c, ^c, o texto normal.
_PATRON = re.compile(r"(_\{[^}]*\}|\^\{[^}]*\}|_[^\s_^{}]|\^[^\s_^{}])")

# Formula corta metida dentro de una frase: `la media $x̄$ se calcula...`.
# Se delimita a proposito: sin delimitador, cualquier guion bajo suelto en una
# palabra normal se leeria como subindice y destrozaria el parrafo.
_INLINE = re.compile(r"\$([^$]+)\$")

# Tamano de letra al dibujar, y resolucion. Mas dpi es mas nitido y pesa poco:
# una formula tipica ronda los 7 KB.
TAMANO_FUENTE = 20
DPI = 220
ANCHO_MAXIMO_PULGADAS = 6.0

_carpeta_temporal: Path | None = None


def _carpeta() -> Path:
    global _carpeta_temporal
    if _carpeta_temporal is None:
        _carpeta_temporal = Path(tempfile.mkdtemp(prefix="formulas_"))
    return _carpeta_temporal


def limpiar_temporales() -> None:
    """Las imagenes quedan incrustadas dentro del .docx, asi que los archivos
    sueltos ya no hacen falta una vez guardado."""
    global _carpeta_temporal
    if _carpeta_temporal is not None:
        import shutil
        shutil.rmtree(_carpeta_temporal, ignore_errors=True)
        _carpeta_temporal = None


def es_formula_destacada(linea: str) -> bool:
    limpia = linea.strip()
    return limpia.startswith(MARCA_DESTACADA) and limpia.endswith(MARCA_DESTACADA) and len(limpia) > 4


def texto_de_formula_destacada(linea: str) -> str:
    return linea.strip()[len(MARCA_DESTACADA):-len(MARCA_DESTACADA)].strip()


def partir_por_formulas_inline(texto: str) -> list[tuple[str, bool]]:
    """Parte el texto en tramos (contenido, es_formula), respetando el orden."""
    partes = []
    ultimo = 0
    for m in _INLINE.finditer(texto):
        if m.start() > ultimo:
            partes.append((texto[ultimo:m.start()], False))
        partes.append((m.group(1), True))
        ultimo = m.end()
    if ultimo < len(texto):
        partes.append((texto[ultimo:], False))
    return partes or [(texto, False)]


def escribir_en_parrafo(paragraph, texto: str, cursiva: bool = True) -> None:
    """Modo texto: subindices y superindices reales, sin imagen."""
    for parte in _PATRON.split(texto):
        if not parte:
            continue
        if parte.startswith("_") or parte.startswith("^"):
            contenido = parte[1:]
            if contenido.startswith("{"):
                contenido = contenido[1:-1]
            run = paragraph.add_run(contenido)
            run.font.subscript = parte.startswith("_")
            run.font.superscript = parte.startswith("^")
        else:
            run = paragraph.add_run(parte)
        run.italic = cursiva


def _renderizar_imagen(latex: str) -> tuple[Path, float] | None:
    """Dibuja la formula y devuelve (ruta, ancho en pulgadas). None si no se pudo."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig = plt.figure(figsize=(0.01, 0.01))
        fig.text(0, 0, f"${latex}$", fontsize=TAMANO_FUENTE)
        destino = _carpeta() / f"f{abs(hash(latex))}.png"
        fig.savefig(destino, dpi=DPI, bbox_inches="tight", pad_inches=0.12, transparent=True)
        plt.close(fig)

        from PIL import Image
        with Image.open(destino) as img:
            ancho = min(img.width / DPI, ANCHO_MAXIMO_PULGADAS)
        return destino, ancho
    except Exception:
        return None


def agregar_formula_destacada(doc, latex: str) -> None:
    """Formula en su propio parrafo, centrada. Intenta imagen y si no, texto."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(8)

    imagen = _renderizar_imagen(latex)
    if imagen is not None:
        ruta, ancho = imagen
        p.add_run().add_picture(str(ruta), width=Inches(ancho))
        return

    escribir_en_parrafo(p, latex)
    for run in p.runs:
        run.font.size = Pt(13)

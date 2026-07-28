"""
Etapa 6 (parte 2): arma el .docx de respaldo de una clase, con diseno pensado
para aprender (tipografia clara, encabezados con color, puntos clave
destacados), no un volcado de texto plano. Combina:
- la nota de fuente limpia y la nota de aprendizaje que genero la skill
  (etapa 4), leidas desde las rutas que la skill reporto
- los 5 conceptos mas repetidos por el profesor (etapa 5)

Se guarda en Output/[Ramo]/<mismo nombre de clase que el audio archivado>.docx
"""
import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from docx.oxml import OxmlElement

from .nombres import nombre_base

COLOR_H1 = RGBColor(0x1F, 0x4E, 0x5F)
COLOR_H2 = RGBColor(0x2E, 0x74, 0x86)
COLOR_DESTACADO_FONDO = "FFF2CC"
COLOR_TABLA_HEADER = "2E7486"

# Partes del kit de repaso pensadas para repaso espaciado en varios dias, que
# no aportan cuando el estudiante tiene solo unas horas antes de la prueba (pidio
# sacarlas del .docx). La nota de Obsidian las sigue teniendo completas, por
# si las usa mas adelante para repaso de largo plazo.
SECCIONES_A_OMITIR_EN_DOCX = ["preguntas de repaso", "plan de repaso"]


def _sombrear_parrafo(paragraph, color_hex: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), color_hex)
    paragraph._p.get_or_add_pPr().append(shd)


def _sombrear_celda(celda, color_hex: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), color_hex)
    celda._tc.get_or_add_tcPr().append(shd)


def _agregar_texto_con_negritas(paragraph, texto: str) -> None:
    partes = re.split(r"(\*\*.+?\*\*)", texto)
    for parte in partes:
        if not parte:
            continue
        if parte.startswith("**") and parte.endswith("**"):
            run = paragraph.add_run(parte[2:-2])
            run.bold = True
        else:
            paragraph.add_run(parte)


def _quitar_frontmatter(md_texto: str) -> str:
    if md_texto.startswith("---"):
        fin = md_texto.find("\n---", 3)
        if fin != -1:
            return md_texto[fin + 4 :].lstrip("\n")
    return md_texto


def _nivel_encabezado(linea: str) -> int | None:
    if linea.startswith("### "):
        return 3
    if linea.startswith("## "):
        return 2
    if linea.startswith("# "):
        return 1
    return None


def _es_fila_tabla(linea: str) -> bool:
    linea = linea.strip()
    return linea.startswith("|") and linea.endswith("|") and len(linea) > 1


def _es_separador_tabla(linea: str) -> bool:
    return bool(re.fullmatch(r"\|[\s\-:|]+\|", linea.strip()))


def _celdas_de_fila(linea: str) -> list[str]:
    interior = linea.strip().strip("|")
    return [c.strip() for c in interior.split("|")]


def _agregar_tabla_markdown(doc: Document, filas: list[list[str]]) -> None:
    if not filas:
        return
    encabezado, *resto = filas
    tabla = doc.add_table(rows=1, cols=len(encabezado))
    tabla.style = "Light Grid Accent 1"
    for celda, texto in zip(tabla.rows[0].cells, encabezado):
        celda.text = texto
        _sombrear_celda(celda, COLOR_TABLA_HEADER)
        for p in celda.paragraphs:
            for run in p.runs:
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                run.bold = True
    for fila in resto:
        celdas = tabla.add_row().cells
        for celda, texto in zip(celdas, fila):
            celda.text = texto


def _agregar_markdown(doc: Document, md_texto: str, saltar_secciones: list[str] | None = None) -> None:
    md_texto = _quitar_frontmatter(md_texto)
    saltar_secciones = [s.lower() for s in (saltar_secciones or [])]
    nivel_saltando: int | None = None

    lineas = md_texto.splitlines()
    i = 0
    while i < len(lineas):
        linea = lineas[i].rstrip()

        nivel = _nivel_encabezado(linea)
        if nivel is not None:
            titulo_encabezado = linea.lstrip("#").strip()
            if nivel_saltando is not None:
                if nivel <= nivel_saltando:
                    nivel_saltando = None
                else:
                    i += 1
                    continue
            if any(s in titulo_encabezado.lower() for s in saltar_secciones):
                nivel_saltando = nivel
                i += 1
                continue

        if nivel_saltando is not None:
            i += 1
            continue

        if not linea.strip():
            i += 1
            continue
        if linea.strip() == "---":
            i += 1
            continue

        if _es_fila_tabla(linea):
            filas = []
            while i < len(lineas) and _es_fila_tabla(lineas[i]):
                if not _es_separador_tabla(lineas[i]):
                    filas.append(_celdas_de_fila(lineas[i]))
                i += 1
            _agregar_tabla_markdown(doc, filas)
            continue

        if linea.startswith("### "):
            h = doc.add_heading(linea[4:], level=3)
        elif linea.startswith("## "):
            h = doc.add_heading(linea[3:], level=2)
            for run in h.runs:
                run.font.color.rgb = COLOR_H2
        elif linea.startswith("# "):
            h = doc.add_heading(linea[2:], level=1)
            for run in h.runs:
                run.font.color.rgb = COLOR_H1
        elif linea.strip().startswith("> [!"):
            texto = re.sub(r"^\s*>\s*\[![a-zA-Z]+\]\s*", "", linea)
            p = doc.add_paragraph()
            _sombrear_parrafo(p, COLOR_DESTACADO_FONDO)
            run = p.add_run(texto)
            run.italic = True
        elif linea.strip().startswith(">"):
            texto = re.sub(r"^\s*>\s*", "", linea)
            p = doc.add_paragraph(style="Intense Quote")
            _agregar_texto_con_negritas(p, texto)
        elif re.match(r"^\s*[-*]\s+", linea):
            texto = re.sub(r"^\s*[-*]\s+", "", linea)
            p = doc.add_paragraph(style="List Bullet")
            _agregar_texto_con_negritas(p, texto)
        elif re.match(r"^\s*\d+\.\s+", linea):
            texto = re.sub(r"^\s*\d+\.\s+", "", linea)
            p = doc.add_paragraph(style="List Number")
            _agregar_texto_con_negritas(p, texto)
        else:
            p = doc.add_paragraph()
            _agregar_texto_con_negritas(p, linea)

        i += 1


def _agregar_conceptos_repetidos(doc: Document, conceptos: list[dict]) -> None:
    h = doc.add_heading("Conceptos mas repetidos por el profesor", level=1)
    for run in h.runs:
        run.font.color.rgb = COLOR_H1
    doc.add_paragraph(
        "Estos conceptos volvieron una y otra vez durante la clase: son candidatos "
        "fuertes para la prueba."
    ).italic = True

    tabla = doc.add_table(rows=1, cols=2)
    tabla.style = "Light Grid Accent 1"
    encabezados = tabla.rows[0].cells
    encabezados[0].text = "Concepto"
    encabezados[1].text = "Por que se repite"
    for celda in encabezados:
        _sombrear_celda(celda, COLOR_TABLA_HEADER)
        for p in celda.paragraphs:
            for run in p.runs:
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                run.bold = True

    for item in conceptos:
        fila = tabla.add_row().cells
        fila[0].text = str(item.get("concepto", ""))
        fila[1].text = str(item.get("por_que", ""))


def generar_docx(
    trabajo: dict,
    titulo: str,
    texto_fuente: str,
    texto_aprendizaje: str,
    conceptos_repetidos: list[dict],
    config: dict,
) -> Path:
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)

    portada = doc.add_heading(f"Clase {trabajo['numero_clase']:02d} - {trabajo['ramo']}", level=0)
    portada.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitulo = doc.add_paragraph(f"{titulo} ({trabajo['fecha']})")
    subtitulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitulo.runs[0].italic = True
    doc.add_page_break()

    if conceptos_repetidos:
        _agregar_conceptos_repetidos(doc, conceptos_repetidos)
        doc.add_page_break()

    if texto_aprendizaje:
        _agregar_markdown(doc, texto_aprendizaje, saltar_secciones=SECCIONES_A_OMITIR_EN_DOCX)
        doc.add_page_break()

    if texto_fuente:
        h = doc.add_heading("Fuente limpia (respaldo)", level=1)
        for run in h.runs:
            run.font.color.rgb = COLOR_H1
        _agregar_markdown(doc, texto_fuente)

    output_dir = Path(config["rutas"]["output"]) / trabajo["ramo"]
    output_dir.mkdir(parents=True, exist_ok=True)
    base = nombre_base(trabajo["numero_clase"], trabajo["fecha"], titulo)
    ruta = output_dir / f"{base}.docx"
    doc.save(str(ruta))
    return ruta

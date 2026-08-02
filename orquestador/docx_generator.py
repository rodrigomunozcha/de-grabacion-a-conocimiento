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
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement

from . import formulas, mapa_visual
from .nombres import nombre_base

COLOR_H1 = RGBColor(0x1F, 0x4E, 0x5F)
COLOR_H2 = RGBColor(0x2E, 0x74, 0x86)
COLOR_DESTACADO_FONDO = "FFF2CC"
COLOR_TABLA_HEADER = "2E7486"

# Partes del kit de repaso pensadas para repaso espaciado en varios dias, que
# no aportan cuando el estudiante tiene solo unas horas antes de la prueba (pidio
# sacarlas del .docx). La nota de Obsidian las sigue teniendo completas, por
# si las usa mas adelante para repaso de largo plazo.
SECCIONES_A_OMITIR_EN_DOCX = [
    "preguntas de repaso",
    "plan de repaso",
    # La sesion por bloques de tiempo dice COMO estudiar; lo que el estudiante
    # necesita en el .docx es la materia ya digerida y con ejemplos, que va en
    # "Materia lista para estudiar" (ver SKILL.md). La sesion sigue completa en
    # la nota de Obsidian para quien quiera organizarse con ella.
    "sesión de estudio",
    "sesion de estudio",
]


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
            formulas.escribir_prosa_con_matematica(paragraph, parte[2:-2], negrita=True)
        else:
            # El texto puede traer formulas cortas delimitadas ($x̄$) y tambien
            # subindices sueltos en medio de la frase, sin delimitar, que es lo
            # que el modelo escribe en la practica (ver formulas.py).
            for trozo, es_formula in formulas.partir_por_formulas_inline(parte):
                if es_formula:
                    formulas.escribir_en_parrafo(paragraph, trozo)
                elif trozo:
                    formulas.escribir_prosa_con_matematica(paragraph, trozo)


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


def _escribir_celda(celda, texto: str) -> None:
    """
    Una celda que es toda una formula se dibuja; el resto va como texto con
    negritas y subindices.

    Antes esto era `celda.text = texto`, o sea texto plano sin ningun formato.
    La tabla de "que formula uso en cada caso" es justo donde mas formulas hay,
    y era el unico lugar del documento donde se veian crudas, con el guion bajo
    y los parentesis a la vista.
    """
    limpio = texto.strip()
    if formulas.parece_solo_formula(limpio):
        crudo = limpio[1:-1] if limpio.startswith("$") and limpio.endswith("$") else limpio
        if formulas.agregar_formula_en_celda(celda, crudo):
            return
    _agregar_texto_con_negritas(celda.paragraphs[0], texto)


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
            _escribir_celda(celda, texto)


def _leer_bloque_cercado(lineas: list[str], i: int) -> tuple[str, int]:
    """Devuelve el contenido de un bloque ``` y la linea siguiente al cierre."""
    i += 1
    dentro = []
    while i < len(lineas) and not lineas[i].strip().startswith("```"):
        dentro.append(lineas[i])
        i += 1
    return "\n".join(dentro), i + 1


def _agregar_mapa(doc: Document, crudo: str) -> None:
    """Dibuja el mapa conceptual. Si los datos vienen mal, no se pone nada: un
    mapa es un extra y no puede costarle el documento a una clase."""
    import json

    try:
        datos = json.loads(crudo)
        ruta = mapa_visual.dibujar(datos.get("centro", ""), datos.get("ramas") or [])
    except Exception:
        ruta = None
    if ruta is None:
        return

    # La nota suele traer su propio encabezado ("Mapa visual") justo antes del
    # bloque. Poner otro encima deja dos titulos seguidos diciendo lo mismo.
    ultimo = doc.paragraphs[-1] if doc.paragraphs else None
    ya_tiene_titulo = (
        ultimo is not None
        and ultimo.style.name.startswith("Heading")
        and "mapa" in ultimo.text.lower()
    )
    if not ya_tiene_titulo:
        h = doc.add_heading("Mapa de la clase", level=1)
        for run in h.runs:
            run.font.color.rgb = COLOR_H1
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(ruta), width=Inches(6.3))


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

        if linea.strip().startswith("```mapa"):
            # El modelo entrega la estructura del mapa como datos; el dibujo lo
            # hace mapa_visual.py. Describir un mapa no es un mapa.
            crudo, i = _leer_bloque_cercado(lineas, i)
            _agregar_mapa(doc, crudo)
            continue

        if formulas.es_formula_destacada(linea):
            formulas.agregar_formula_destacada(doc, formulas.texto_de_formula_destacada(linea))
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


COLOR_CONTEXTO_FONDO = "EAF3F7"


def _agregar_contexto_previo(doc: Document, texto: str) -> None:
    """
    Va al principio del documento, antes que nada del contenido de la clase.

    Existe porque una clase sobre algo nuevo se escucha sin red: el profesor da
    por sabido lo que vio en cursos anteriores, y el estudiante que no lo tiene
    fresco pierde la primera media hora tratando de ubicarse. Esta seccion se
    lee primero y da justo el piso necesario para que el resto se entienda.

    Es lo unico del documento que NO sale de la transcripcion, asi que se
    marca como tal: el resto del material vale porque es lo que el profesor
    dijo, y esa distincion no se puede difuminar.
    """
    h = doc.add_heading("Antes de empezar: lo que conviene tener claro", level=1)
    for run in h.runs:
        run.font.color.rgb = COLOR_H1

    aviso = doc.add_paragraph()
    _sombrear_parrafo(aviso, COLOR_CONTEXTO_FONDO)
    run = aviso.add_run(
        "Esta seccion no es parte de la clase: es contexto agregado para que lo "
        "que viene se entienda desde cero. Leela primero."
    )
    run.italic = True

    _agregar_markdown(doc, texto)


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
    texto_contexto: str = "",
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

    if texto_contexto:
        _agregar_contexto_previo(doc, texto_contexto)
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
    # Las imagenes ya quedaron incrustadas en el .docx.
    formulas.limpiar_temporales()
    mapa_visual.limpiar_temporales()
    return ruta

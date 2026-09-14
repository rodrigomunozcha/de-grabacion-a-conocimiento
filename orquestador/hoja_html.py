"""
Hoja de repaso de una clase, en HTML autocontenido. Reemplaza al .docx.

Por que existe. El .docx de cada clase tenia entre 20 y 25 paginas y el
estudiante no los abria: para la Solemne 1 de Sistemas y de Termodinamica
(septiembre de 2026) estudio con hojas de repaso que armo a mano en
conversaciones aparte, y fueron esas las que uso de verdad. Esta etapa genera
ese formato para cada clase.

El diseno sale de esas hojas: paleta Solarized, tarjetas con un color de
significado fijo, marcas de procedencia en cada afirmacion, graficos en SVG
dibujados a mano, formulas en MathML e impresion en blanco y negro. Dos cambios,
uno pedido y otro encontrado:

  - Siempre en modo oscuro. Las hojas originales seguian la configuracion del
    Mac, y el estudiante pidio oscuro fijo con impresion que ahorre tinta.
  - La negrita monoespaciada de las hojas originales era falsa: el archivo de
    peso 700 era identico byte a byte al de 400, asi que se veia regular. Aqui
    se incrustan solo los dos archivos reales (latin y latin extendido) y la
    negrita la arma el navegador.

Por que una llamada al modelo y no una conversion. Condensar veinte paginas en
una o dos exige elegir que se queda, y eso es criterio, no formato. El .docx se
armaba sin modelo, asi que esta es una llamada nueva por clase. Se mide igual
que las otras, en logs/uso.jsonl con la etapa "hoja", para que su costo quede a
la vista.

Por que sin herramientas. La etapa recibe las notas dentro del prompt y
devuelve texto. No necesita leer ni escribir nada, y no darle herramientas es la
unica configuracion que no depende de que un gate este bien escrito: el texto de
las notas deriva de una grabacion y no es una fuente confiable. El SDK pasa el
prompt por la entrada estandar (--input-format stream-json), asi que el largo de
las notas no choca con el limite de argumentos del sistema.

Por que el HTML se sanea aqui. Por lo mismo: lo que devuelve el modelo termina
en un archivo que se abre en el navegador. Se filtra con lista blanca de
etiquetas y atributos, nunca con lista negra, y se descarta cualquier recurso
externo. La hoja queda autocontenida por construccion, no por buena voluntad del
modelo.

Lo que arma Python y no el modelo: la cabecera (ramo, numero, fecha), el pie y
la tarjeta "Lo que el profesor pidio". Son los datos que no se pueden inventar y
la seccion que mas se cree. Esa tarjeta ademas corrige un error real del .docx:
cuando la skill no reportaba los llamados (quedaban en null), el documento decia
"el profesor no anuncio fechas ni evaluacion" aunque la nota de aprendizaje si
los traia. Paso en cuatro clases. En Sistemas del 01-09-2026 el .docx negaba el
anuncio de la prueba del martes siguiente y de los capitulos que entraban. Aqui
la tarjeta sale de la nota, y si no hay de donde sacarla dice que no se pudo
comprobar, que no es lo mismo que no haber anuncios.

Si el modelo falla, la hoja se escribe igual con lo que arma Python y un aviso
visible de que falta la materia condensada. Nunca una hoja que parezca completa
sin serlo.

Uso para clases ya procesadas:
    python3 -m orquestador.hoja_html <slug> [<slug>...] [--pisar]
"""
import base64
import html
import json
import re
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from .config import cargar_config, dir_pendientes
from .nombres import nombre_base
from .skill_runner import CLI_PATH, PROJECT_ROOT, describir_error_sdk, normalizar_resultado
from .uso import registrar_uso

DIR_PLANTILLA = Path(__file__).parent / "plantilla_hoja"
RUTA_ESTILOS = DIR_PLANTILLA / "estilos.css"
RUTA_INSTRUCCIONES = DIR_PLANTILLA / "instrucciones.md"
DIR_FUENTES = DIR_PLANTILLA / "fuentes"

MARCA_INICIO = "===HOJA_INICIO==="
MARCA_FIN = "===HOJA_FIN==="

# La etapa no usa herramientas, asi que la respuesta cabe en un turno. El tope
# es un seguro contra una corrida que se desvie, no un objetivo (ver
# orquestador/CLAUDE.md sobre max_turns).
MAX_TURNS = 3
TIMEOUT_SEGUNDOS = 15 * 60

# Por debajo de esto la hoja no tiene materia de verdad, aunque el modelo haya
# devuelto las marcas. Se trata como falla para que el aviso sea visible, en
# vez de guardar una hoja casi vacia que se ve terminada.
MINIMO_PALABRAS = 80

# Con permission_mode="bypassPermissions", dejar una herramienta fuera de
# allowed_tools no la bloquea: solo disallowed_tools lo hace (verificado en
# vivo, ver orquestador/CLAUDE.md). Aqui no hace falta ninguna.
HERRAMIENTAS_PROHIBIDAS = [
    "Bash", "Read", "Write", "Edit", "NotebookEdit", "Glob", "Grep",
    "WebFetch", "WebSearch", "Task", "TodoWrite",
]


# --------------------------------------------------------------------------
# Saneado del HTML que devuelve el modelo
# --------------------------------------------------------------------------

ETIQUETAS_HTML = frozenset(
    "section div header footer h2 h3 h4 p span b strong i em u small sub sup code pre "
    "ul ol li table thead tbody tfoot tr th td caption br hr figure figcaption "
    "blockquote dl dt dd abbr mark kbd".split()
)
ETIQUETAS_SVG = frozenset(
    "svg g line path rect circle ellipse polyline polygon text tspan defs marker "
    "title desc".split()
)
ETIQUETAS_MATHML = frozenset(
    "math semantics annotation mrow mi mn mo ms mtext mspace msub msup msubsup mfrac "
    "msqrt mroot mover munder munderover mtable mtr mtd mstyle mpadded mphantom "
    "menclose merror".split()
)
VACIAS = frozenset({"br", "hr"})
# Estas se eliminan con todo su contenido. Las demas etiquetas no permitidas se
# desenvuelven: se pierde la etiqueta pero se conserva el texto, que casi
# siempre es materia.
DESCARTAR_CON_CONTENIDO = frozenset(
    "script style iframe object embed noscript template textarea select form head".split()
)

ATRIBUTOS_COMUNES = frozenset(
    {"class", "lang", "role", "aria-label", "aria-hidden", "colspan", "rowspan", "scope", "title"}
)
# html.parser entrega los nombres de atributo en minusculas, y SVG distingue
# mayusculas (viewBox, refX). Se guarda el nombre correcto para escribirlo bien.
ATRIBUTOS_SVG = {
    n.lower(): n
    for n in (
        "viewBox width height x y x1 y1 x2 y2 cx cy r rx ry d points dx dy "
        "fill stroke stroke-width stroke-dasharray stroke-linecap stroke-linejoin "
        "opacity fill-opacity stroke-opacity font-size font-weight font-family "
        "font-style text-anchor dominant-baseline letter-spacing transform "
        "marker-start marker-mid marker-end markerWidth markerHeight refX refY "
        "orient markerUnits id preserveAspectRatio"
    ).split()
}
ATRIBUTOS_MATHML = {
    n.lower(): n
    for n in (
        "display encoding mathvariant stretchy fence separator lspace rspace accent "
        "accentunder width height depth columnalign rowspacing columnspacing "
        "displaystyle scriptlevel form largeop movablelimits symmetric minsize "
        "maxsize linethickness notation"
    ).split()
}

# Cualquier valor que pueda traer un recurso de afuera o ejecutar algo. Se
# compara sin espacios para que "java script:" no pase. Las referencias locales
# de SVG (url(#flecha) en marker-end) si son validas y se conservan.
_VALOR_PELIGROSO = re.compile(r"javascript:|vbscript:|data:|https?:|//|expression\(|@import", re.I)
_URL_NO_LOCAL = re.compile(r"url\((?![\"']?#)", re.I)


def _valor_seguro(valor: str) -> bool:
    compacto = re.sub(r"\s+", "", valor or "")
    return not (_VALOR_PELIGROSO.search(compacto) or _URL_NO_LOCAL.search(compacto))


class _Saneador(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.salida: list[str] = []
        self.pila: list[str] = []
        self.descartando = 0

    def _permitida(self, tag: str) -> bool:
        if tag in ETIQUETAS_SVG:
            return tag == "svg" or "svg" in self.pila
        if tag in ETIQUETAS_MATHML:
            return tag == "math" or "math" in self.pila
        return tag in ETIQUETAS_HTML

    def _atributos(self, tag: str, attrs) -> str:
        if tag in ETIQUETAS_SVG:
            propios = ATRIBUTOS_SVG
        elif tag in ETIQUETAS_MATHML:
            propios = ATRIBUTOS_MATHML
        else:
            propios = {}
        partes = []
        for nombre, valor in attrs:
            nombre = (nombre or "").lower()
            if nombre in ATRIBUTOS_COMUNES:
                canonico = nombre
            elif nombre in propios:
                canonico = propios[nombre]
            else:
                continue  # incluye style, href, src y todos los on*
            valor = "" if valor is None else str(valor)
            if not _valor_seguro(valor):
                continue
            partes.append(f' {canonico}="{html.escape(valor, quote=True)}"')
        return "".join(partes)

    def handle_starttag(self, tag, attrs):
        if self.descartando:
            if tag in DESCARTAR_CON_CONTENIDO:
                self.descartando += 1
            return
        if tag in DESCARTAR_CON_CONTENIDO:
            self.descartando = 1
            return
        if not self._permitida(tag):
            return
        self.salida.append(f"<{tag}{self._atributos(tag, attrs)}>")
        if tag not in VACIAS:
            self.pila.append(tag)

    def handle_startendtag(self, tag, attrs):
        if self.descartando or tag in DESCARTAR_CON_CONTENIDO or not self._permitida(tag):
            return
        atributos = self._atributos(tag, attrs)
        self.salida.append(f"<{tag}{atributos}>" if tag in VACIAS else f"<{tag}{atributos}></{tag}>")

    def handle_endtag(self, tag):
        if self.descartando:
            if tag in DESCARTAR_CON_CONTENIDO:
                self.descartando -= 1
            return
        if tag not in self.pila:
            return
        while self.pila:
            abierta = self.pila.pop()
            self.salida.append(f"</{abierta}>")
            if abierta == tag:
                break

    def handle_data(self, data):
        if not self.descartando:
            self.salida.append(html.escape(data, quote=False))

    def resultado(self) -> str:
        self.close()
        while self.pila:
            self.salida.append(f"</{self.pila.pop()}>")
        return "".join(self.salida)


def sanear_html(fragmento: str) -> str:
    saneador = _Saneador()
    saneador.feed(fragmento or "")
    return saneador.resultado()


def contar_palabras_visibles(fragmento: str) -> int:
    """Palabras que se leen, sin contar el texto de graficos ni formulas."""
    sin_figuras = re.sub(r"<(svg|math)\b.*?</\1>", " ", fragmento or "", flags=re.S | re.I)
    return len(html.unescape(re.sub(r"<[^>]+>", " ", sin_figuras)).split())


# --------------------------------------------------------------------------
# Lo que arma Python
# --------------------------------------------------------------------------

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def _fecha_legible(iso: str | None) -> str:
    try:
        d = date.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return str(iso or "")
    return f"{_DIAS[d.weekday()]} {d.day} de {_MESES[d.month - 1]} de {d.year}"


def _md_en_linea(texto: str) -> str:
    t = html.escape(texto.strip(), quote=False)
    # Un enlace de Obsidian no funciona fuera del vault: queda el nombre de la nota,
    # en cursiva. Antes salia tal cual, con los corchetes (Desempeno 02-09-2026).
    t = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"<i>\2</i>", t)
    t = re.sub(r"\[\[([^\]]+)\]\]", r"<i>\1</i>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", t)


_SECCION_PIDIO = re.compile(r"^## Lo que el profesor pidi[oó][^\n]*\n(.*?)(?=^## |\Z)", re.S | re.M)
_VINETA = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")

MARCA_CL = '<span class="f cl">CL</span>'
MARCA_DUDA = '<span class="f duda">?</span>'


_SUBTITULO_EN_NEGRITA = re.compile(r"^\*\*(.+?)\*\*\s*:?\s*$")
# Las formas en que la skill declara que un punto no quedo confirmado. Un punto
# asi no puede llevar la marca CL ("dicho en esta clase") sin mas: la marca
# contradiria el texto que tiene al lado.
_INCIERTO = re.compile(
    r"seguro:\**\s*no|no seguro|\(dudoso|reconstrucci[oó]n|profe no fue claro|poco clar|sin confirmar",
    re.I,
)


def _elementos_de_la_nota(seccion: str) -> list[tuple[str, str]]:
    """
    Recorre la seccion en orden y la devuelve como una lista de elementos:
    ("subtitulo", texto), ("vineta", texto), ("parrafo", texto) o
    ("advertencia", texto).

    La primera version agrupaba por subtitulo y escribia todos los parrafos
    antes que todas las vinetas. Fallo con las notas reales de Desempeno
    Organizacional (12-08 y 26-08-2026): la skill no siempre escribe los
    subtitulos como "### Avisos", a veces los escribe como una linea en negrita
    ("**Entra en evaluacion:**"). Esas lineas caian como parrafos, los dos
    subtitulos quedaban arriba y todas las vinetas juntas abajo, asi que no se
    distinguia que entraba en la prueba y que era un aviso. Justo la distincion
    que la tarjeta existe para dar. Tambien partia en fragmentos sueltos un
    callout de varias lineas.

    Por eso se conserva el orden de la nota tal cual, las dos formas de escribir
    un subtitulo cuentan como subtitulo, y las lineas que siguen a una vineta,
    un parrafo o un callout se pegan a ese mismo elemento.
    """
    elementos: list[tuple[str, str]] = []
    abierto: str | None = None
    for linea in seccion.splitlines():
        limpia = linea.strip()
        if not limpia:
            abierto = None
            continue
        if limpia.startswith("### "):
            elementos.append(("subtitulo", limpia[4:].strip().rstrip(":")))
            abierto = None
            continue
        if limpia.startswith(">"):
            contenido = re.sub(r"^>\s*(\[![^\]]+\]\s*)?", "", limpia)
            if abierto == "advertencia":
                elementos[-1] = ("advertencia", f"{elementos[-1][1]} {contenido}".strip())
            else:
                elementos.append(("advertencia", contenido))
                abierto = "advertencia"
            continue
        if _VINETA.match(linea):
            elementos.append(("vineta", _VINETA.sub("", linea, count=1).strip()))
            abierto = "vineta"
            continue
        if abierto in ("vineta", "parrafo"):
            # Antes de reconocer subtitulos en negrita, a proposito. En la nota
            # del 12-08 la advertencia "**(seguro: no, el tramo del audio esta
            # cortado...)**" iba en negrita en la linea siguiente de su vineta.
            # Leida como subtitulo, le quitaba la duda a esa vineta, que salia
            # marcada CL, y colgaba la vineta siguiente de un titulo falso. Una
            # linea en negrita solo es subtitulo si no hay nada abierto, igual
            # que en Markdown.
            tipo, texto = elementos[-1]
            elementos[-1] = (tipo, f"{texto} {limpia}")
            continue
        negrita = _SUBTITULO_EN_NEGRITA.match(limpia)
        if negrita:
            elementos.append(("subtitulo", negrita.group(1).strip().rstrip(":")))
            abierto = None
        else:
            elementos.append(("parrafo", limpia))
            abierto = "parrafo"
    return elementos


def tarjeta_lo_que_pidio(texto_aprendizaje: str, llamados: dict | None) -> str:
    """
    La tarjeta que mas se cree, armada sin modelo.

    Tres casos que no pueden verse iguales:
      - La nota trae la seccion: se muestra en el mismo orden que la nota, con
        sus citas textuales. Lo que la nota declara no confirmado lleva la marca
        de verificar, no la de "dicho en clase".
      - La nota no la trae pero hay llamados comprobados: se muestran esos, y si
        vienen vacios se dice que no hubo anuncios, porque eso si se comprobo.
      - Ni una cosa ni la otra: se dice que no se pudo comprobar. Decir aqui
        "no anuncio nada" seria el error que ya cometio el .docx.
    """
    cabecera = '<div class="t pro plena pidio"><h3><span class="n">!</span>Lo que el profesor pidió</h3>'
    m = _SECCION_PIDIO.search(texto_aprendizaje or "")
    elementos = _elementos_de_la_nota(m.group(1)) if m else []

    if elementos:
        partes = [cabecera]
        lista_abierta = False
        for tipo, texto in elementos:
            if tipo != "vineta" and lista_abierta:
                partes.append("</ul>")
                lista_abierta = False
            if tipo == "subtitulo":
                partes.append(f'<span class="clave">{_md_en_linea(texto)}</span>')
            elif tipo == "vineta":
                if not lista_abierta:
                    partes.append("<ul>")
                    lista_abierta = True
                marca = MARCA_DUDA if _INCIERTO.search(texto) else MARCA_CL
                partes.append(f"<li>{_md_en_linea(texto)}{marca}</li>")
            elif tipo == "advertencia":
                partes.append(f'<p class="mini">{_md_en_linea(texto)}{MARCA_DUDA}</p>')
            else:
                partes.append(f'<p class="mini">{_md_en_linea(texto)}</p>')
        if lista_abierta:
            partes.append("</ul>")
        return "".join(partes) + "</div>"

    if isinstance(llamados, dict):
        avisos = [a for a in (llamados.get("avisos") or []) if a.get("que")]
        evaluacion = [e for e in (llamados.get("evaluacion") or []) if e.get("tema")]
        if not avisos and not evaluacion:
            return (cabecera + "<p>En esta clase el profesor no anunció fechas, entregas ni "
                    "contenidos de evaluación.</p></div>")
        partes = [cabecera]
        for titulo, items, campo in (("Avisos", avisos, "que"), ("Evaluación", evaluacion, "tema")):
            if not items:
                continue
            partes.append(f'<span class="clave">{titulo}</span><ul>')
            for item in items:
                texto = html.escape(str(item.get(campo, "")).strip())
                cuando = html.escape(str(item.get("cuando", "") or "").strip())
                textual = html.escape(str(item.get("textual", "") or "").strip())
                linea = f"<b>{texto}</b>" + (f" ({cuando})" if cuando else "")
                if textual:
                    linea += f' <span class="cita">"{textual}"</span>'
                marca = MARCA_CL if item.get("seguro", True) else MARCA_DUDA
                partes.append(f"<li>{linea}{marca}</li>")
            partes.append("</ul>")
        return "".join(partes) + "</div>"

    return (cabecera + "<p>No se pudo comprobar qué pidió el profesor en esta clase."
            f"{MARCA_DUDA} Eso no significa que no haya anunciado nada: revisa la nota de fuente "
            "en Obsidian antes de dar por hecho que no hubo fechas ni evaluaciones.</p></div>")


def _tarjeta_sin_materia(motivo: str | None, slug: str) -> str:
    return (
        '<section class="bloque"><div class="t err plena"><h3><span class="n">!</span>'
        "Falta la materia condensada</h3>"
        f"<p>No se pudo redactar esta parte de la hoja: {html.escape(motivo or 'motivo desconocido')}. "
        "Eso no significa que la clase no tenga materia. El desarrollo completo está en la nota "
        "de aprendizaje en Obsidian.</p>"
        f'<p class="mini">Para intentarlo de nuevo: <code>python3 -m orquestador.hoja_html '
        f"{html.escape(slug)}</code></p></div></section>"
    )


def _css_fuentes() -> str:
    """
    Los .woff2 no estan en el repositorio (ver .gitignore). Si faltan, la hoja
    usa la monoespaciada del sistema: se ve casi igual y no se rompe nada.
    """
    reglas = []
    for archivo in sorted(DIR_FUENTES.glob("*.woff2")):
        ruta_rango = archivo.parent / f"{archivo.name}.rango"
        rango = ruta_rango.read_text(encoding="utf-8").strip() if ruta_rango.exists() else ""
        datos = base64.b64encode(archivo.read_bytes()).decode("ascii")
        regla = ("@font-face{font-family:'Atkinson Mono';font-style:normal;font-weight:400;"
                 f"font-display:swap;src:url(data:font/woff2;base64,{datos}) format('woff2')")
        reglas.append(regla + (f";unicode-range:{rango}" if rango else "") + "}")
    return "\n".join(reglas)


def armar_documento(
    trabajo: dict,
    titulo: str,
    cuerpo: str | None,
    tarjeta_pidio: str,
    nombre_nota: str = "",
    motivo_fallo: str | None = None,
    slug: str = "",
) -> str:
    e = lambda s: html.escape(str(s or ""), quote=True)  # noqa: E731
    ramo = trabajo.get("ramo") or ""
    numero = trabajo.get("numero_clase")
    etiqueta = f"Clase {int(numero):02d}" if str(numero).isdigit() else "Clase"
    fuentes = _css_fuentes()
    if cuerpo is None:
        cuerpo = _tarjeta_sin_materia(motivo_fallo, slug)

    tipografia = (
        "la tipografía Atkinson Hyperlegible Mono va incrustada y los gráficos son SVG"
        if fuentes else "los gráficos son SVG y la tipografía es la del sistema"
    )
    origen_nota = f" ({e(nombre_nota)})" if nombre_nota else ""

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>{e(titulo)} - {e(ramo)}</title>
<style>
{fuentes}
{RUTA_ESTILOS.read_text(encoding="utf-8")}
</style>
</head>
<body>
<div class="hoja">
<header class="cab">
  <p class="ramo">{e(ramo)} &middot; {etiqueta} &middot; {e(_fecha_legible(trabajo.get("fecha")))}</p>
  <h1>{e(titulo)}</h1>
  <p class="sub">Hoja de repaso de esta clase. El desarrollo completo está en la nota de aprendizaje de Obsidian.</p>
  <p class="leyenda"><b>Cada afirmación dice de dónde sale.</b> <b>CL</b> dicho en esta clase &nbsp;&middot;&nbsp; <b>?</b> dudoso por audio o reconstruido, conviene verificar &nbsp;&middot;&nbsp; <b>+</b> agregado aquí, no se dijo en clase</p>
</header>
{tarjeta_pidio}
{cuerpo}
<p class="pie">
  Fuente: las notas procesadas de la clase del {e(_fecha_legible(trabajo.get("fecha")))}{origen_nota}, revisadas contra la grabación. Lo marcado con <b>+</b> es agregado y se señala uno por uno para que no se confunda con materia dictada.
  <br>Generada el {datetime.now():%d-%m-%Y}. Sin dependencias de red: {tipografia}, así que se ve igual sin conexión.
</p>
</div>
</body>
</html>
"""


def ruta_de_hoja(trabajo: dict, titulo: str, config: dict, sufijo: str = "") -> Path:
    base = nombre_base(trabajo["numero_clase"], trabajo["fecha"], titulo)
    return Path(config["rutas"]["output"]) / trabajo["ramo"] / f"{base}{sufijo}.html"


def escribir_hoja(ruta: Path, documento: str) -> Path:
    """Solo escribe. Es lo unico de esta etapa que va dentro de la seccion
    critica de finalizar_clase: dura milisegundos. La redaccion, que tarda
    minutos, va antes y se puede abortar."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(documento, encoding="utf-8")
    return ruta


# --------------------------------------------------------------------------
# La llamada al modelo
# --------------------------------------------------------------------------

def _construir_prompt(ramo, titulo, fecha, conceptos, texto_aprendizaje, texto_fuente, texto_contexto) -> str:
    partes = [
        f"Ramo: {ramo}",
        f"Fecha de la clase: {fecha}",
        f"Título: {titulo}",
        "",
        "Conceptos que el profesor más repitió, según el análisis de la clase:",
        json.dumps(conceptos or [], ensure_ascii=False),
        "",
        "===NOTA DE APRENDIZAJE===",
        texto_aprendizaje or "(no existe)",
        "===FIN DE LA NOTA===",
        "",
        "===NOTA DE FUENTE===",
        texto_fuente or "(no existe)",
        "===FIN DE LA NOTA===",
    ]
    if texto_contexto:
        partes += ["", "===NOTA DE CONTEXTO===", texto_contexto, "===FIN DE LA NOTA==="]
    partes += [
        "",
        f"Redacta la hoja siguiendo tus instrucciones. Devuelve solo el HTML entre "
        f"{MARCA_INICIO} y {MARCA_FIN}.",
    ]
    return "\n".join(partes)


def _extraer_cuerpo(texto: str) -> str | None:
    inicio = texto.find(MARCA_INICIO)
    fin = texto.rfind(MARCA_FIN)
    if inicio == -1 or fin == -1 or fin <= inicio:
        return None
    fragmento = texto[inicio + len(MARCA_INICIO):fin].strip()
    # A veces lo envuelve en un bloque de codigo aunque se le pida que no.
    fragmento = re.sub(r"^```(?:html)?\s*|\s*```$", "", fragmento)
    return fragmento or None


# El modelo a veces usa el subtitulo (.clave, que va en su propia linea) como
# etiqueta de una frase: <span class="clave">Dato</span>: texto. En la hoja la
# linea de abajo empezaba con dos puntos o con un punto (Desempeno 26-08-2026,
# tres veces). Las instrucciones ya lo piden distinto, pero la hoja no puede
# depender de que el modelo obedezca.
_PUNTUACION_TRAS_SUBTITULO = re.compile(r'(<span class="clave">[^<]*</span>)\s*[:.,]\s*')
# Y a veces mete dentro de la marca la frase de lo que hay que verificar. La marca
# se imprime chica, en mono y en superindice, asi que la frase quedaba casi
# ilegible (Desempeno 26-08-2026, cuatro veces). La frase sale de la marca y queda
# antes de ella, como texto normal.
_MARCA_CON_TEXTO = re.compile(r'<span class="f (duda|cl|mas)">\s*(\?|CL|\+)\s*([^<]*?[^<\s])\s*</span>')


def pulir_cuerpo(cuerpo: str) -> str:
    """Corrige dos usos del modelo que se ven mal en la hoja. No cambia el contenido."""
    cuerpo = _PUNTUACION_TRAS_SUBTITULO.sub(r"\1", cuerpo)

    def sacar_de_la_marca(m: re.Match) -> str:
        tipo, signo, texto = m.groups()
        if m.string[:m.start()].rstrip()[-1:] in (".", "!", "?"):
            texto = texto[0].upper() + texto[1:]
        if texto[-1] not in ".!?)":
            texto += "."
        return f' {texto}<span class="f {tipo}">{signo}</span>'

    return _MARCA_CON_TEXTO.sub(sacar_de_la_marca, cuerpo)


async def redactar_cuerpo(
    texto_aprendizaje: str,
    texto_fuente: str,
    texto_contexto: str,
    conceptos: list,
    ramo: str,
    titulo: str,
    fecha: str,
    slug: str,
) -> tuple[str | None, str | None]:
    """
    Devuelve (cuerpo saneado, None) o (None, motivo). Nunca decide por su
    cuenta que la clase no tiene materia: eso lo dice el motivo, en palabras.

    Mismo patron que las otras etapas: no se hace raise ni return dentro del
    bucle del SDK. Si el modelo alcanzo a devolver la hoja completa, vale
    aunque despues llegue un error de la API (ver orquestador/CLAUDE.md).
    """
    if not ((texto_aprendizaje or "").strip() or (texto_fuente or "").strip()):
        return None, "no se encontraron las notas de la clase en el vault"

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        setting_sources=[],
        system_prompt=RUTA_INSTRUCCIONES.read_text(encoding="utf-8"),
        allowed_tools=[],
        disallowed_tools=HERRAMIENTAS_PROHIBIDAS,
        permission_mode="bypassPermissions",
        cli_path=str(CLI_PATH),
        max_turns=MAX_TURNS,
    )

    partes: list[str] = []
    error_sdk = None
    prompt = _construir_prompt(
        ramo, titulo, fecha, conceptos, texto_aprendizaje, texto_fuente, texto_contexto
    )
    async for mensaje in query(prompt=prompt, options=options):
        if isinstance(mensaje, AssistantMessage):
            for bloque in mensaje.content:
                if isinstance(bloque, TextBlock):
                    partes.append(bloque.text)
        elif isinstance(mensaje, ResultMessage):
            registrar_uso("hoja", slug, mensaje)
            if mensaje.is_error:
                error_sdk = describir_error_sdk(mensaje)

    crudo = _extraer_cuerpo("\n".join(partes))
    if crudo is None:
        motivo = (f"hubo un problema de conexión ({error_sdk})" if error_sdk
                  else "el modelo no devolvió la hoja")
        return None, motivo

    cuerpo = pulir_cuerpo(sanear_html(crudo))
    if contar_palabras_visibles(cuerpo) < MINIMO_PALABRAS:
        return None, "la hoja salió prácticamente vacía"
    return cuerpo, None


# --------------------------------------------------------------------------
# Para clases ya procesadas
# --------------------------------------------------------------------------

async def generar_para_clase(slug: str, config: dict, pisar: bool = False) -> tuple[Path, int, str | None]:
    """
    Arma la hoja de una clase que ya paso por el pipeline, desde sus notas. No
    transcribe ni vuelve a analizar la clase: solo paga la redaccion.

    Sin `pisar` nunca reemplaza una hoja existente: escribe una copia al lado.
    """
    # Import local: finalizar_clase importa este modulo, y la comprobacion de
    # que la nota esta dentro del vault vive alla (una sola implementacion).
    from .finalizar_clase import _leer_nota

    ruta_meta = dir_pendientes() / f"{slug}.json"
    ruta_skill = dir_pendientes() / f"{slug}_skill.json"
    if not ruta_meta.is_file() or not ruta_skill.is_file():
        raise FileNotFoundError(
            f"Falta {ruta_meta.name} o {ruta_skill.name}. Esa clase no esta procesada."
        )

    trabajo = json.loads(ruta_meta.read_text(encoding="utf-8"))
    resultado = normalizar_resultado(
        json.loads(ruta_skill.read_text(encoding="utf-8")), trabajo["ramo"]
    )
    vault_dir = config["rutas"]["vault_obsidian"]
    aprendizaje = _leer_nota(resultado.get("aprendizaje"), vault_dir)
    fuente = _leer_nota(resultado.get("fuente"), vault_dir)
    contexto = _leer_nota(resultado.get("contexto"), vault_dir)
    titulo = resultado["titulo"]

    cuerpo, motivo = await redactar_cuerpo(
        aprendizaje, fuente, contexto, resultado.get("conceptos_repetidos") or [],
        trabajo["ramo"], titulo, trabajo["fecha"], slug,
    )
    documento = armar_documento(
        trabajo, titulo, cuerpo, tarjeta_lo_que_pidio(aprendizaje, resultado.get("llamados")),
        Path(resultado.get("aprendizaje") or "").name, motivo, slug,
    )
    ruta = ruta_de_hoja(trabajo, titulo, config)
    if ruta.exists() and not pisar:
        ruta = ruta_de_hoja(trabajo, titulo, config, " (nueva)")
    escribir_hoja(ruta, documento)
    return ruta, contar_palabras_visibles(cuerpo or ""), motivo


if __name__ == "__main__":
    import sys

    import anyio

    slugs = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not slugs:
        disponibles = sorted(
            p.stem.replace("_skill", "") for p in dir_pendientes().glob("*_skill.json")
        )
        print("Uso: python3 -m orquestador.hoja_html <slug> [<slug>...] [--pisar]")
        print("\n  Arma la hoja de repaso de una clase ya procesada, desde sus notas.")
        print("  Cuesta una llamada al modelo por clase (no transcribe ni reanaliza).")
        print("  --pisar   reemplaza la hoja existente en vez de escribir una copia al lado")
        print("\nClases procesadas disponibles:")
        for s in disponibles:
            print(f"  {s}")
        raise SystemExit(1)

    _config = cargar_config()
    for _slug in slugs:
        print(f"\n{_slug}")

        async def _una(s=_slug):
            with anyio.fail_after(TIMEOUT_SEGUNDOS):
                return await generar_para_clase(s, _config, "--pisar" in sys.argv)

        _ruta, _palabras, _motivo = anyio.run(_una)
        print(f"  -> {_ruta}")
        if _motivo:
            print(f"  AVISO: la hoja salio sin la materia condensada ({_motivo}).")
        else:
            print(f"  {_palabras} palabras visibles")

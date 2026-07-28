"""
Extrae las 10 preguntas y respuestas modelo de la nota de aprendizaje que
genera la skill transcripciones-a-conocimiento, para convertirlas en
flashcards. Se apoya en el formato fijo de la skill (ver
.claude/skills/transcripciones-a-conocimiento/references/formato-obsidian.md):
una seccion "## ... preguntas ..." con items numerados, y una seccion
"## ... respuestas ..." aparte, tambien numerada, en el mismo orden.
"""
import re


def _seccion(texto: str, patron_encabezado: str) -> str:
    match = re.search(patron_encabezado, texto, re.IGNORECASE)
    if not match:
        return ""
    resto = texto[match.end():]
    fin = re.search(r"\n#{1,6}\s", resto)
    return resto[: fin.start()] if fin else resto


def _items_numerados(seccion: str) -> list[str]:
    """Ignora cualquier texto antes del primer item numerado (ej. la
    instruccion "(de menor a mayor dificultad...)" que la skill suele dejar
    debajo del encabezado): sin esto, esa linea se colaba como si fuera la
    pregunta o respuesta numero 1 (visto en vivo)."""
    items = []
    actual: list[str] | None = None
    for linea in seccion.splitlines():
        m = re.match(r"\s*\d+[.)]\s+(.*)", linea)
        if m:
            if actual is not None:
                items.append(" ".join(actual).strip())
            actual = [m.group(1).strip()]
        elif linea.strip() and actual is not None:
            actual.append(linea.strip())
    if actual is not None:
        items.append(" ".join(actual).strip())
    return items


def extraer_preguntas_respuestas(texto_aprendizaje: str) -> list[tuple[str, str]]:
    seccion_preguntas = _seccion(texto_aprendizaje, r"#{1,6}[^\n]*regunta[^\n]*\n")
    seccion_respuestas = _seccion(texto_aprendizaje, r"#{1,6}[^\n]*espuesta[^\n]*\n")
    preguntas = _items_numerados(seccion_preguntas)
    respuestas = _items_numerados(seccion_respuestas)
    return list(zip(preguntas, respuestas))

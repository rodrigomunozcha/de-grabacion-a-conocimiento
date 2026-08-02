"""
Etapa de revision: una segunda pasada, independiente, sobre lo que escribio
la skill, antes de que eso se convierta en .docx y en flashcards de Anki.

Por que existe. La skill hace todo en una sola corrida (limpiar, destilar,
preguntar, responder) y nadie mira el resultado antes de que se archive como
material de estudio. El riesgo real no es que quede feo, es que quede
convincente y falso: la transcripcion viene de audio de sala, tiene tramos
inaudibles y errores del transcriptor, y el mismo modelo que rellena esos
huecos es el que despues decide si su trabajo quedo bien. Un dato inventado
que se cuela aca no queda en un archivo cualquiera: termina memorizado en
Anki y estudiado como si fuera lo que dijo el profe.

Por eso el revisor corre como una llamada aparte y no como una autocritica
dentro de la misma sesion. Llega sin haber escrito nada, sin compromiso con
el texto propio, y su unico trabajo es comparar las notas contra la
transcripcion cruda. Un modelo revisando su propia salida en la misma
conversacion tiende a ratificarla.

El revisor no corrige. Solo lee (herramienta Read y nada mas) y reporta.
Quien corrige es la sesion original de la skill, que ya tiene todo el
contexto en memoria (ver skill_runner.corregir_con_revision). Asi la
correccion no vuelve a pagar la lectura completa de la transcripcion, y el
revisor no puede estropear notas que ya estaban bien.
"""
import json
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    query,
)

from .config import dir_pendientes
from .skill_runner import CLI_PATH, PROJECT_ROOT, construir_gate_de_rutas
from .uso import registrar_uso


MARCADOR_REVISION = "RESULTADO_REVISION:"

# El revisor lee tres archivos y contesta. Una corrida normal usa menos de
# 10 turnos; esto es el corte por si se queda dando vueltas.
MAX_TURNS = 25

SYSTEM_PROMPT = """\
Eres el revisor de un sistema que convierte grabaciones de clases universitarias
en material de estudio. Otro agente ya limpio la transcripcion y escribio dos
notas. Tu trabajo es comparar esas notas contra la transcripcion cruda y reportar
lo que esta mal. No escribes ni corriges nada: solo lees y reportas.

Lo que buscas, en orden de importancia:

1. Contenido inventado. Afirmaciones, definiciones, cifras, formulas o ejemplos
   que estan en las notas y no tienen respaldo en la transcripcion. Este es el
   fallo mas grave: la nota alimenta flashcards que el estudiante va a memorizar.
2. Respuestas modelo que contradicen la clase o que se apoyan en teoria general
   en vez de en lo que el profe efectivamente enseño.
3. Reconstrucciones presentadas como textuales. Graficos de pizarra, formulas y
   logica que el agente infirio del habla deben ir marcados como reconstruccion a
   verificar. Si van sin marca, es un hallazgo.
4. Huecos tapados. Tramos donde la transcripcion no permite recuperar lo que paso
   y la nota los rellena con algo que suena solido en vez de señalarlos.
5. Contenido importante de la clase que la nota dejo fuera.
6. Los cinco conceptos repetidos: deben ser los que el profe vuelve a tocar una y
   otra vez, no los que a ti te parecen mas importantes.

Lo que NO reportas: estilo, redaccion, orden de las secciones, largo de la nota,
preferencias de formato. Nada cosmetico.

Gravedad:
- "alta": el estudiante estudiaria algo falso o al reves de lo que dijo el profe.
- "media": queda peor de lo que podria, pero nada de lo que dice es falso.

Se estricto con "alta" y no la uses para inflar el reporte. Si las notas estan
bien, decirlo es la respuesta correcta y esperada. Reporta como maximo 8
hallazgos, los mas graves primero. Para cada uno, se concreto sobre donde esta y
que hay que hacer: quien te lee va a aplicar la correccion sin volver a leerlo
todo.

Escribe en español claro y directo. Sin guion largo. Evita el punto y coma.
"""


def _construir_prompt(
    ruta_transcripcion: str,
    ruta_fuente: str,
    ruta_aprendizaje: str,
    ramo: str,
    conceptos: list[dict],
) -> str:
    conceptos_texto = "\n".join(
        f"  {i}. {c.get('concepto', '?')}: {c.get('por_que', '')}"
        for i, c in enumerate(conceptos, start=1)
    ) or "  (no se reportaron)"

    return (
        f"Revisa el material de una clase del ramo {ramo}.\n\n"
        "Lee estos tres archivos completos antes de opinar:\n"
        f"1. Transcripcion cruda (la unica fuente de verdad): {ruta_transcripcion}\n"
        f"2. Nota de fuente limpia: {ruta_fuente}\n"
        f"3. Nota de aprendizaje (la que genera las flashcards): {ruta_aprendizaje}\n\n"
        "Los cinco conceptos que el agente reporto como los mas repetidos por el "
        f"profe:\n{conceptos_texto}\n\n"
        "Cuando termines, la ultima linea de tu respuesta debe ser exactamente esta, "
        "sin nada mas en esa linea y con JSON valido en una sola linea:\n"
        'RESULTADO_REVISION: {"veredicto": "aprobado" | "corregir", "hallazgos": '
        '[{"gravedad": "alta" | "media", "donde": "nota y seccion exacta", '
        '"problema": "que esta mal y por que", "correccion": "que hay que hacer"}]}\n\n'
        'Usa "corregir" solo si hay al menos un hallazgo de gravedad alta. '
        'Si todo lo que encontraste es de gravedad media, el veredicto es "aprobado" '
        "y los hallazgos quedan igual en la lista, como registro."
    )


def _parsear_revision(texto: str) -> dict | None:
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea.startswith(MARCADOR_REVISION):
            continue
        try:
            revision = json.loads(linea[len(MARCADOR_REVISION):].strip())
        except json.JSONDecodeError:
            return None
        hallazgos = revision.get("hallazgos")
        if not isinstance(hallazgos, list):
            revision["hallazgos"] = []
        if revision.get("veredicto") not in ("aprobado", "corregir"):
            # Sin veredicto legible, se decide por los hallazgos: es preferible
            # gastar una correccion de mas que archivar algo falso.
            revision["veredicto"] = (
                "corregir" if hallazgos_graves(revision) else "aprobado"
            )
        return revision
    return None


def hallazgos_graves(revision: dict) -> list[dict]:
    return [h for h in revision.get("hallazgos", []) if h.get("gravedad") == "alta"]


def hallazgos_para_avisar(revision: dict, se_corrigio: bool) -> list[dict]:
    """
    Los hallazgos que el estudiante tiene que ver, porque nadie los arreglo.

    Existe porque el revisor era la etapa mas cara despues del destilado y su
    resultado terminaba en un JSON que nadie abria: se pagaba por una revision
    invisible. Los de gravedad alta se corrigen solos, asi que solo hace falta
    avisar de los que quedaron en pie. Si la correccion no llego a aplicarse,
    los graves tambien entran, porque entonces siguen ahi.
    """
    hallazgos = revision.get("hallazgos", [])
    if se_corrigio:
        return [h for h in hallazgos if h.get("gravedad") != "alta"]
    return list(hallazgos)


def _guardar_revision(slug: str, revision: dict) -> Path:
    dir_pendientes().mkdir(parents=True, exist_ok=True)
    ruta = dir_pendientes() / f"{slug}_revision.json"
    ruta.write_text(json.dumps(revision, indent=2, ensure_ascii=False), encoding="utf-8")
    return ruta


async def revisar(
    ruta_transcripcion: str,
    resultado_skill: dict,
    ramo: str,
    vault_dir: str,
    slug: str,
) -> dict:
    """
    Devuelve {"veredicto": ..., "hallazgos": [...]}.

    Si el revisor no llega a emitir su linea de resultado, devuelve veredicto
    "aprobado" con la razon anotada en vez de reventar: las notas ya estan
    escritas y son utiles, y una revision fallida no es motivo para perder la
    clase entera. Queda registrado en el JSON de revision para poder revisarlo
    despues.
    """
    prompt = _construir_prompt(
        ruta_transcripcion,
        resultado_skill.get("fuente", ""),
        resultado_skill.get("aprendizaje", ""),
        ramo,
        resultado_skill.get("conceptos_repetidos") or [],
    )

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        # El revisor no usa la skill ni ninguna configuracion del proyecto: es
        # un lector con una sola tarea. Sin setting_sources arranca mas liviano.
        setting_sources=[],
        system_prompt=SYSTEM_PROMPT,
        # Solo lectura. Read basta porque las tres rutas van en el prompt, no
        # tiene que buscar nada. Menos herramientas es tambien menos tokens de
        # definiciones en cada turno.
        allowed_tools=["Read"],
        # Igual que en skill_runner: con "bypassPermissions" no basta con dejar
        # una herramienta fuera de allowed_tools, hay que prohibirla.
        disallowed_tools=["Bash", "Write", "Edit", "NotebookEdit"],
        permission_mode="bypassPermissions",
        hooks={
            "PreToolUse": [
                HookMatcher(
                    matcher="Read",
                    hooks=[construir_gate_de_rutas(vault_dir)],
                )
            ]
        },
        cli_path=str(CLI_PATH),
        max_turns=MAX_TURNS,
    )

    partes = []
    error_sdk = None
    async for mensaje in query(prompt=prompt, options=options):
        if isinstance(mensaje, AssistantMessage):
            for bloque in mensaje.content:
                if isinstance(bloque, TextBlock):
                    partes.append(bloque.text)
        elif isinstance(mensaje, ResultMessage):
            registrar_uso("revision", slug, mensaje)
            if mensaje.is_error:
                error_sdk = mensaje.subtype

    revision = _parsear_revision("\n".join(partes))
    if revision is None:
        revision = {
            "veredicto": "aprobado",
            "hallazgos": [],
            "revision_fallida": error_sdk or "el revisor no emitio RESULTADO_REVISION",
        }

    _guardar_revision(slug, revision)
    return revision


if __name__ == "__main__":
    import sys

    import anyio

    if len(sys.argv) != 5:
        print(
            "Uso: python3 -m orquestador.revisor <ruta_transcripcion> "
            "<ruta_skill_json> <ramo> <vault_dir>"
        )
        raise SystemExit(1)

    ruta_skill_json = Path(sys.argv[2])
    resultado = json.loads(ruta_skill_json.read_text(encoding="utf-8"))
    slug = ruta_skill_json.stem.replace("_skill", "")

    revision = anyio.run(revisar, sys.argv[1], resultado, sys.argv[3], sys.argv[4], slug)
    print(json.dumps(revision, indent=2, ensure_ascii=False))

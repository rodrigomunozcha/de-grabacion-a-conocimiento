"""
Invoca la skill transcripciones-a-conocimiento via Claude Agent SDK, con el
ramo y el alcance ya resueltos por el orquestador, para que no se detenga a
preguntar nada de eso. Esta es la unica invocacion del SDK por clase: hace
todo el trabajo que "requiere criterio" en una sola pasada (limpieza,
destilado, preguntas y respuestas modelo, titulo, los 5 conceptos mas
repetidos, y guardado en el vault de Obsidian).

Antes esto eran 3 invocaciones separadas (titulo, skill, conceptos
repetidos). Cada invocacion del SDK paga un overhead fijo de ~16.000 tokens
de system prompt (medido en vivo) antes de leer nada, ademas de releer la
transcripcion completa cada vez. Fusionarlas en una sola ahorra ese costo
dos veces por clase.

La skill vive en .claude/skills/transcripciones-a-conocimiento dentro de
este proyecto (copiada del plugin original y adaptada para invocacion
automatizada, ver el SKILL.md). El SDK la descubre porque cwd apunta a la
raiz del proyecto y setting_sources incluye "project" (no hace falta "user":
verificado en vivo que la skill se sigue encontrando igual, y asi la corrida
no depende de configuracion global de la cuenta que podria cambiar sin aviso).

Al terminar, la skill reporta todo en una linea "RESULTADO_ORQUESTADOR: {...}"
(instruccion en el SKILL.md), que esta etapa parsea y guarda.
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
from .uso import registrar_uso

PROJECT_ROOT = Path(__file__).parent.parent
CLI_PATH = PROJECT_ROOT / "node_modules" / ".bin" / "claude"

MARCADOR_RESULTADO = "RESULTADO_ORQUESTADOR:"

# Nombre de la skill, tal como aparece en el campo `name` de su SKILL.md.
SKILL = "transcripciones-a-conocimiento"

# Tope de turnos como seguro: si algo se sale de lo esperado (ej. la skill
# queda dando vueltas releyendo archivos), esto corta la corrida en vez de
# consumir cuota sin control. Una clase normal usa muchos menos.
#
# Estaba en 40 y se quedo corto en una clase real (visto en vivo): la skill
# alcanzo a escribir las tres notas en el vault y se quedo sin turnos justo
# antes de emitir la linea RESULTADO_ORQUESTADOR, asi que el orquestador dio
# la corrida por fallida aunque el trabajo estaba hecho. Con vaults grandes
# hay que explorar mas antes de escribir.
MAX_TURNS = 80


def construir_gate_de_rutas(vault_dir: str):
    """
    Hook PreToolUse que acota al agente a las dos carpetas donde legitimamente
    tiene algo que hacer: este proyecto (la transcripcion a leer y los archivos
    de la propia skill) y el vault de Obsidian (donde escribe las notas).

    Existe porque la corrida es automatizada y usa permission_mode
    "bypassPermissions": nadie va a ver ni contestar una peticion de permiso,
    asi que sin esto Write/Edit podrian escribir en cualquier parte del disco
    (verificado en vivo que si pueden). La transcripcion viene de audio de sala
    de clases pasado por un transcriptor automatico, o sea texto no confiable
    que termina dentro del prompt: si alguna vez trajera algo que el modelo
    interprete como instruccion, esto limita el alcance del dano.

    Se usa un hook y no can_use_tool porque el propio SDK avisa que
    can_use_tool queda anulado por "bypassPermissions" y por las entradas de
    allowed_tools que habilitan una herramienta completa (verificado en vivo:
    el callback nunca se llega a invocar). El hook si se dispara, y decide
    solo, sin preguntarle nada a nadie: la automatizacion queda intacta.

    Lo usa tambien la etapa de revision (ver revisor.py), que corre con las
    mismas dos raices.
    """
    raices = [PROJECT_ROOT.resolve(), Path(vault_dir).expanduser().resolve()]

    async def gate(input_data, tool_use_id, context):
        tool_input = input_data.get("tool_input") or {}
        # Write/Edit/Read usan "file_path"; Glob y Grep usan "path".
        ruta = tool_input.get("file_path") or tool_input.get("path") or ""
        if not ruta:
            return {}
        destino = Path(ruta).expanduser().resolve()
        if any(destino == raiz or destino.is_relative_to(raiz) for raiz in raices):
            return {}
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Ruta fuera de alcance: {destino}. Esta corrida solo puede leer y "
                    f"escribir dentro del proyecto ({raices[0]}) y del vault de Obsidian "
                    f"({raices[1]})."
                ),
            }
        }

    return gate


def _construir_prompt(ruta_texto: str, ramo: str, carpeta_ramo: str) -> str:
    # La carpeta llega ya resuelta y creada por el orquestador (ver
    # carpetas.py). Darsela exacta, y decirle explicitamente que no busque, es
    # lo que evita que liste el vault entero: ese listado entraba al contexto y
    # se releia en cada turno posterior.
    return (
        f"Aplica la skill {SKILL} sobre la transcripcion "
        f"que esta en el archivo: {ruta_texto}\n\n"
        "Contexto ya resuelto por el sistema de orquestacion, no lo preguntes:\n"
        f"- Ramo: {ramo}\n"
        "- Alcance: una clase (esta unica transcripcion)\n"
        f"- Carpeta donde van las notas: {carpeta_ramo}\n\n"
        "Esa carpeta ya existe y es la correcta. Escribe las notas ahi directamente. "
        "No explores el vault de Obsidian ni busques la carpeta del ramo, ya esta "
        "resuelta. Si necesitas ver que otras notas del ramo hay para enlazarlas, "
        "mira solo dentro de esa carpeta."
    )


def _parsear_resultado(texto: str) -> dict | None:
    for linea in texto.splitlines():
        linea = linea.strip()
        if linea.startswith(MARCADOR_RESULTADO):
            try:
                resultado = json.loads(linea[len(MARCADOR_RESULTADO):].strip())
            except json.JSONDecodeError:
                return None
            # Si vinieron el titulo y las rutas pero los conceptos repetidos
            # quedaron mal formados, no se pierde toda la corrida por eso:
            # el .docx se arma igual, sin esa seccion (ver finalizar_clase.py).
            conceptos = resultado.get("conceptos_repetidos")
            if not isinstance(conceptos, list):
                resultado["conceptos_repetidos"] = []
            return resultado
    return None


def _guardar_resultado_skill(slug: str, resultado: dict | None) -> Path:
    dir_pendientes().mkdir(parents=True, exist_ok=True)
    ruta = dir_pendientes() / f"{slug}_skill.json"
    ruta.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    return ruta


async def aplicar_skill(
    ruta_texto: str, ramo: str, vault_dir: str, slug: str, carpeta_ramo: str
) -> dict | None:
    """
    Corre la skill y devuelve lo que reporto, mas el campo "session_id" que
    agrega el orquestador (no viene del modelo): con el, la etapa de revision
    puede pedirle a esta misma sesion que corrija sin volver a leer la
    transcripcion completa. Ver corregir_con_revision.

    `carpeta_ramo` es la carpeta exacta donde van las notas, ya resuelta y
    creada (ver carpetas.py). `vault_dir` se sigue necesitando aparte, para el
    gate de rutas: acota la escritura a todo el vault, no solo a esa carpeta,
    porque la skill puede tener razones legitimas para leer notas de otros
    ramos al enlazar.
    """
    prompt = _construir_prompt(ruta_texto, ramo, carpeta_ramo)
    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        # La skill se habilita por nombre en la opcion `skills`, no metiendo
        # "Skill" en allowed_tools (esa forma quedo deprecada). Asi el permiso
        # queda acotado a esta skill en vez de habilitar cualquiera que el CLI
        # llegue a descubrir.
        skills=[SKILL],
        # El SDK rellena setting_sources solo si no viene puesto (verificado en
        # el codigo del transporte: usa ["user", "project"] por defecto). Aqui
        # va explicito para que siga siendo solo "project": asi la corrida no
        # depende de configuracion global de la cuenta, que podria cambiar sin
        # aviso.
        setting_sources=["project"],
        # Glob y Grep son de solo lectura y hacen falta de verdad: la skill los
        # usa para ubicar la carpeta del ramo dentro del vault antes de escribir
        # (verificado en vivo). Bash no aparece aca, pero eso por si solo NO lo
        # bloquea: con permission_mode "bypassPermissions" el modelo igual puede
        # usar herramientas que no esten en esta lista (comprobado en vivo, la
        # skill escribia las notas con Bash). Lo que si lo bloquea de verdad es
        # disallowed_tools, abajo.
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        # Sin Bash, el gate de rutas de abajo tiene sentido: si el modelo pudiera
        # ejecutar comandos, podria escribir donde quisiera sin pasar por el.
        # Verificado en vivo que la skill funciona igual sin Bash (usa Write).
        disallowed_tools=["Bash"],
        permission_mode="bypassPermissions",
        hooks={
            "PreToolUse": [
                HookMatcher(
                    matcher="Write|Edit|Read|Glob|Grep",
                    hooks=[construir_gate_de_rutas(vault_dir)],
                )
            ]
        },
        cli_path=str(CLI_PATH),
        max_turns=MAX_TURNS,
    )

    partes = []
    session_id = None
    async for mensaje in query(prompt=prompt, options=options):
        if isinstance(mensaje, AssistantMessage):
            for bloque in mensaje.content:
                if isinstance(bloque, TextBlock):
                    partes.append(bloque.text)
        elif isinstance(mensaje, ResultMessage):
            registrar_uso("destilado", slug, mensaje)
            session_id = mensaje.session_id
            if mensaje.is_error:
                raise RuntimeError(f"La skill termino con error: {mensaje.subtype}")

    resultado = _parsear_resultado("\n".join(partes))
    if resultado is None:
        raise ValueError(
            "La skill no reporto RESULTADO_ORQUESTADOR, no se puede ubicar "
            "las notas ni los conceptos repetidos."
        )

    resultado["session_id"] = session_id
    _guardar_resultado_skill(slug, resultado)
    return resultado


def _construir_prompt_correccion(hallazgos: list[dict]) -> str:
    lineas = []
    for i, h in enumerate(hallazgos, start=1):
        lineas.append(
            f"{i}. [{h.get('gravedad', 'alta')}] {h.get('donde', 'sin ubicacion')}\n"
            f"   Problema: {h.get('problema', '')}\n"
            f"   Correccion pedida: {h.get('correccion', '')}"
        )
    detalle = "\n".join(lineas)

    return (
        "Un revisor independiente comparo las notas que escribiste contra la "
        "transcripcion cruda y encontro esto:\n\n"
        f"{detalle}\n\n"
        "Corrige estos puntos en las notas que ya escribiste, editandolas en el "
        "mismo lugar. Instrucciones:\n"
        "- Si un hallazgo es correcto, arreglalo. Cuando la transcripcion no "
        "respalda algo, la salida correcta casi nunca es reescribirlo mejor: es "
        "quitarlo o marcarlo (reconstruccion a verificar, dudoso: audio, hueco).\n"
        "- Si un hallazgo esta equivocado y la transcripcion te da la razon, no "
        "cambies nada por ese punto y explica en una linea por que.\n"
        "- No reescribas secciones enteras ni cambies el estilo. Toca solo lo "
        "señalado.\n"
        "- No inventes contenido nuevo para tapar lo que quites.\n\n"
        "Cuando termines, vuelve a emitir la linea RESULTADO_ORQUESTADOR con el "
        "mismo formato de antes (titulo, fuente, aprendizaje, conceptos_repetidos), "
        "actualizada si alguna correccion la cambio."
    )


async def corregir_con_revision(
    resultado_skill: dict, hallazgos: list[dict], vault_dir: str, slug: str
) -> dict:
    """
    Tercera pasada: le devuelve los hallazgos del revisor a la misma sesion que
    escribio las notas, para que las corrija.

    Se retoma la sesion original (`resume`) en vez de abrir una nueva por dos
    razones. La primera es de costo: esa sesion ya leyo la transcripcion entera
    y tiene las notas en contexto, asi que corregir no vuelve a pagar esa
    lectura. La segunda es de calidad: sabe de donde salio cada parrafo, asi que
    puede distinguir un hallazgo correcto de uno donde el revisor se equivoco.

    Si la correccion falla por cualquier motivo, se devuelve el resultado
    original sin tocar. Las notas ya escritas siguen ahi y la clase se archiva
    igual: perder la correccion es un problema mucho menor que perder la clase.
    """
    if not hallazgos:
        return resultado_skill

    session_id = resultado_skill.get("session_id")
    if not session_id:
        return resultado_skill

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        skills=[SKILL],
        setting_sources=["project"],
        resume=session_id,
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        disallowed_tools=["Bash"],
        permission_mode="bypassPermissions",
        hooks={
            "PreToolUse": [
                HookMatcher(
                    matcher="Write|Edit|Read|Glob|Grep",
                    hooks=[construir_gate_de_rutas(vault_dir)],
                )
            ]
        },
        cli_path=str(CLI_PATH),
        # Bastante mas bajo que el de la primera pasada: aca son ediciones
        # puntuales sobre notas que ya existen, no el trabajo completo. Si se
        # pasa de esto, algo se salio de lo esperado y es mejor cortar.
        max_turns=30,
    )

    partes = []
    async for mensaje in query(
        prompt=_construir_prompt_correccion(hallazgos), options=options
    ):
        if isinstance(mensaje, AssistantMessage):
            for bloque in mensaje.content:
                if isinstance(bloque, TextBlock):
                    partes.append(bloque.text)
        elif isinstance(mensaje, ResultMessage):
            registrar_uso("correccion", slug, mensaje)
            if mensaje.is_error:
                return resultado_skill

    corregido = _parsear_resultado("\n".join(partes))
    if corregido is None:
        # Las correcciones pueden haberse aplicado igual (el modelo edita antes
        # de reportar). Se conservan las rutas y el titulo que ya se tenian.
        return resultado_skill

    corregido["session_id"] = session_id
    corregido["corregido_tras_revision"] = True
    _guardar_resultado_skill(slug, corregido)
    return corregido


if __name__ == "__main__":
    import sys

    import anyio

    if len(sys.argv) != 5:
        print("Uso: python3 -m orquestador.skill_runner <ruta_texto> <ramo> <vault_dir> <slug>")
        raise SystemExit(1)

    from .carpetas import resolver_carpeta_ramo
    from .config import cargar_config, guardar_config

    _config = cargar_config()
    _carpeta, _cambio = resolver_carpeta_ramo(sys.argv[2], sys.argv[3], _config)
    if _cambio:
        guardar_config(_config)

    resultado = anyio.run(
        aplicar_skill, sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], str(_carpeta)
    )
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

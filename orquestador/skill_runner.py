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

PROJECT_ROOT = Path(__file__).parent.parent
CLI_PATH = PROJECT_ROOT / "node_modules" / ".bin" / "claude"
PENDIENTES_DIR = Path(__file__).parent / "transcripciones_pendientes"

MARCADOR_RESULTADO = "RESULTADO_ORQUESTADOR:"

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


def _construir_gate_de_rutas(vault_dir: str):
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


def _construir_prompt(ruta_texto: str, ramo: str, vault_dir: str) -> str:
    return (
        "Aplica la skill transcripciones-a-conocimiento sobre la transcripcion "
        f"que esta en el archivo: {ruta_texto}\n\n"
        "Contexto ya resuelto por el sistema de orquestacion, no lo preguntes:\n"
        f"- Ramo: {ramo}\n"
        "- Alcance: una clase (esta unica transcripcion)\n"
        f"- Vault de Obsidian: {vault_dir}\n\n"
        "Guarda las notas en ese vault, en la carpeta de ese ramo."
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
    PENDIENTES_DIR.mkdir(parents=True, exist_ok=True)
    ruta = PENDIENTES_DIR / f"{slug}_skill.json"
    ruta.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    return ruta


async def aplicar_skill(ruta_texto: str, ramo: str, vault_dir: str, slug: str) -> dict | None:
    prompt = _construir_prompt(ruta_texto, ramo, vault_dir)
    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        setting_sources=["project"],
        # Glob y Grep son de solo lectura y hacen falta de verdad: la skill los
        # usa para ubicar la carpeta del ramo dentro del vault antes de escribir
        # (verificado en vivo). Bash no aparece aca, pero eso por si solo NO lo
        # bloquea: con permission_mode "bypassPermissions" el modelo igual puede
        # usar herramientas que no esten en esta lista (comprobado en vivo, la
        # skill escribia las notas con Bash). Lo que si lo bloquea de verdad es
        # disallowed_tools, abajo.
        allowed_tools=["Skill", "Read", "Write", "Edit", "Glob", "Grep"],
        # Sin Bash, el gate de rutas de abajo tiene sentido: si el modelo pudiera
        # ejecutar comandos, podria escribir donde quisiera sin pasar por el.
        # Verificado en vivo que la skill funciona igual sin Bash (usa Write).
        disallowed_tools=["Bash"],
        permission_mode="bypassPermissions",
        hooks={
            "PreToolUse": [
                HookMatcher(
                    matcher="Write|Edit|Read|Glob|Grep",
                    hooks=[_construir_gate_de_rutas(vault_dir)],
                )
            ]
        },
        cli_path=str(CLI_PATH),
        max_turns=MAX_TURNS,
    )

    partes = []
    async for mensaje in query(prompt=prompt, options=options):
        if isinstance(mensaje, AssistantMessage):
            for bloque in mensaje.content:
                if isinstance(bloque, TextBlock):
                    partes.append(bloque.text)
        elif isinstance(mensaje, ResultMessage):
            if mensaje.is_error:
                raise RuntimeError(f"La skill termino con error: {mensaje.subtype}")

    resultado = _parsear_resultado("\n".join(partes))
    if resultado is None:
        raise ValueError(
            "La skill no reporto RESULTADO_ORQUESTADOR, no se puede ubicar "
            "las notas ni los conceptos repetidos."
        )

    _guardar_resultado_skill(slug, resultado)
    return resultado


if __name__ == "__main__":
    import sys

    import anyio

    if len(sys.argv) != 5:
        print("Uso: python3 -m orquestador.skill_runner <ruta_texto> <ramo> <vault_dir> <slug>")
        raise SystemExit(1)

    resultado = anyio.run(aplicar_skill, sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

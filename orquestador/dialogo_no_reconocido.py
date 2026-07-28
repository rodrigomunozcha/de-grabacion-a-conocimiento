"""
Ventana de dialogo nativa de macOS para cuando un audio cae en un dia que no
esta en la tabla dia->ramo (ej. sabado, o cualquier dia fuera de lunes-viernes,
o grabaciones corruptas con fecha antigua). Usa AppleScript via osascript,
sin dependencias nuevas.

El dialogo principal tiene un timeout de 10 minutos: si el estudiante no esta
cerca del Mac para contestar, se trata igual que si hubiera elegido "Ignorar
archivo" (verificado en vivo que "giving up after" funciona asi con
"display dialog"). "choose from list" y el dialogo de texto (para elegir o
escribir el ramo) no soportan "giving up after" (probado, da error de
sintaxis), asi que esos esperan sin limite de tiempo: solo aparecen despues
de que el estudiante ya eligio activamente "Transcribir y aplicar skills
completas".

Ramos que no estan en el horario actual (ej. un ramo de intercambio en otro
idioma) se pueden agregar a mano la primera vez: quedan
guardados en config["ramos_adicionales"] para no tener que volver a escribirlos
ni elegir el idioma de nuevo la proxima vez que aparezca ese mismo ramo.
"""
import re
import subprocess

from .config import ETIQUETAS_PERFIL_WHISPER, guardar_config

TIMEOUT_DIALOGO_SEGUNDOS = 600

OPCION_SOLO_TRANSCRIBIR = "Solo transcribir"
OPCION_APLICAR_SKILLS = "Transcribir y aplicar skills completas"
OPCION_IGNORAR = "Ignorar archivo"
OPCIONES = [OPCION_SOLO_TRANSCRIBIR, OPCION_APLICAR_SKILLS, OPCION_IGNORAR]

OPCION_RAMO_NUEVO = "Otro (ramo nuevo)..."


def _escapar(texto: str) -> str:
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _mostrar_dialogo_principal(trabajo: dict) -> str | None:
    archivos = ", ".join(a.split("/")[-1] for a in trabajo["archivos"])
    mensaje = (
        f"La grabacion del {trabajo['dia_semana']} {trabajo['fecha']} "
        f"({archivos}) no corresponde a ningun ramo de tu horario.\n\n"
        "Que quieres hacer con ella?"
    )
    lista_botones = ", ".join(_escapar(o) for o in OPCIONES)
    script = (
        f"display dialog {_escapar(mensaje)} "
        f"buttons {{{lista_botones}}} "
        f"default button {_escapar(OPCION_IGNORAR)} "
        f'with title "Grabacion sin clasificar" '
        f"giving up after {TIMEOUT_DIALOGO_SEGUNDOS}"
    )
    resultado = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if resultado.returncode != 0:
        return None  # cancelado (Esc / cerrar ventana) o error, tratar como no resuelto
    m = re.search(r"button returned:([^,]*), gave up:(true|false)", resultado.stdout.strip())
    if not m:
        return None
    boton, gave_up = m.group(1), m.group(2)
    if gave_up == "true" or not boton:
        return None
    return boton


def _elegir_de_lista(opciones: list[str], prompt: str) -> str | None:
    lista = ", ".join(_escapar(o) for o in opciones)
    script = f"choose from list {{{lista}}} with prompt {_escapar(prompt)} with title \"Grabacion sin clasificar\""
    resultado = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if resultado.returncode != 0:
        return None
    salida = resultado.stdout.strip()
    return None if salida == "false" else salida


def _pedir_texto(prompt: str, respuesta_default: str = "") -> str | None:
    """None significa que cancelo (Esc / boton Cancelar). "" es una respuesta
    valida (el campo quedo vacio a proposito, ej. un contexto opcional)."""
    script = (
        f"display dialog {_escapar(prompt)} default answer {_escapar(respuesta_default)} "
        f'with title "Grabacion sin clasificar"'
    )
    resultado = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if resultado.returncode != 0:
        return None
    m = re.search(r"text returned:(.*)$", resultado.stdout.strip())
    if not m:
        return None
    return m.group(1).strip()


def _crear_ramo_nuevo(config: dict) -> tuple[str, str, str] | None:
    nombre = _pedir_texto("Escribe el nombre del ramo (ej. INTERNATIONAL BUSINESS MANAGEMENT):")
    if not nombre:
        return None

    etiqueta_idioma = _elegir_de_lista(
        list(ETIQUETAS_PERFIL_WHISPER.keys()), "En que idioma se dicta esta clase?"
    )
    if etiqueta_idioma is None:
        return None
    perfil_whisper = ETIQUETAS_PERFIL_WHISPER[etiqueta_idioma]

    contexto = _pedir_texto(
        "Terminos, nombres o jerga que el profesor use seguido, para que Whisper "
        "los transcriba mejor (opcional, dejalo vacio si no aplica):"
    )
    if contexto is None:
        return None

    config.setdefault("ramos_adicionales", {})[nombre] = {
        "perfil_whisper": perfil_whisper,
        "contexto": contexto,
    }
    guardar_config(config)
    return nombre, perfil_whisper, contexto


def _elegir_ramo(config: dict) -> tuple[str, str, str] | None:
    ramos_horario = {r["nombre"]: {"perfil_whisper": r["perfil_whisper"], "contexto": ""} for r in config["ramos"].values()}
    ramos_adicionales = config.get("ramos_adicionales", {})
    info_por_ramo = {**ramos_horario, **ramos_adicionales}

    opciones = sorted(info_por_ramo.keys()) + [OPCION_RAMO_NUEVO]
    elegido = _elegir_de_lista(opciones, "Elige el ramo para esta grabacion:")
    if elegido is None:
        return None

    if elegido == OPCION_RAMO_NUEVO:
        return _crear_ramo_nuevo(config)

    info = info_por_ramo[elegido]
    return elegido, info["perfil_whisper"], info.get("contexto", "")


def preguntar_que_hacer(trabajo: dict, config: dict) -> dict:
    boton = _mostrar_dialogo_principal(trabajo)

    if boton == OPCION_SOLO_TRANSCRIBIR:
        return {"accion": "solo_transcribir"}

    if boton == OPCION_APLICAR_SKILLS:
        seleccion = _elegir_ramo(config)
        if seleccion is None:
            return {"accion": "ignorar"}
        ramo, perfil_whisper, contexto = seleccion
        return {
            "accion": "aplicar_skills",
            "ramo": ramo,
            "perfil_whisper": perfil_whisper,
            "contexto": contexto,
        }

    return {"accion": "ignorar"}

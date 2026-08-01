import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

# Carpeta de los archivos intermedios entre etapas (<slug>.txt, <slug>.json,
# <slug>_skill.json, <slug>_revision.json).
#
# Se resuelve por funcion y no como constante en cada modulo porque el modo
# ensayo la redirige a un sandbox (ver ensayo.py). Sin eso, un ensayo dejaba
# un <slug>_skill.json en la carpeta real, y ese archivo es justo la marca de
# "esta clase ya se proceso": la siguiente corrida de verdad se habria saltado
# la clase en silencio, sin notas y sin error.
PENDIENTES_DIR_POR_DEFECTO = Path(__file__).parent / "transcripciones_pendientes"

_dir_pendientes = PENDIENTES_DIR_POR_DEFECTO


def dir_pendientes() -> Path:
    return _dir_pendientes


def usar_dir_pendientes(ruta: Path | str | None) -> None:
    """Redirige la carpeta de intermedios. Con None vuelve a la real."""
    global _dir_pendientes
    _dir_pendientes = Path(ruta) if ruta else PENDIENTES_DIR_POR_DEFECTO

PERFILES_WHISPER_VALIDOS = ["es-chile", "es-spain", "es-neutro", "en", "acento-mixto"]

# Etiquetas legibles para mostrar en el dialogo nativo (ver dialogo_no_reconocido.py)
# cuando se agrega un ramo nuevo que no esta en la tabla dia->ramo (ej. un ramo
# de intercambio en otro idioma).
ETIQUETAS_PERFIL_WHISPER = {
    "Español (Chile)": "es-chile",
    "Español (España)": "es-spain",
    "Español (neutro)": "es-neutro",
    "Inglés": "en",
    "Acento mixto (hablante no nativo)": "acento-mixto",
}

DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes"]

# Solo son el valor sugerido que ve quien corre setup.py por primera vez
# (Enter para aceptarlo, o escribe el ramo real). Se guardan en config.json,
# que no se sube al repo.
RAMOS_POR_DEFECTO = {
    "lunes": "NOMBRE DEL RAMO DEL LUNES",
    "martes": "NOMBRE DEL RAMO DEL MARTES",
    "miercoles": "NOMBRE DEL RAMO DEL MIERCOLES",
    "jueves": "NOMBRE DEL RAMO DEL JUEVES",
    "viernes": "NOMBRE DEL RAMO DEL VIERNES",
}


def cargar_config() -> dict:
    if not CONFIG_PATH.exists():
        raise RuntimeError(
            "No existe orquestador/config.json todavia. "
            "Corre primero: python3 orquestador/setup.py"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")

"""
Configuracion inicial del orquestador de estudio.
Correr con: python3 -m orquestador.setup (desde la carpeta "Claude Code")
Se puede volver a correr cuando algo cambie (rutas, horario, fecha de semestre).
"""
from datetime import datetime
from pathlib import Path

from .config import (
    CONFIG_PATH,
    DIAS_SEMANA,
    PERFILES_WHISPER_VALIDOS,
    RAMOS_POR_DEFECTO,
    cargar_config,
    guardar_config,
)

DEFAULTS_RUTAS = {
    "input": "~/Documents/Claude Code/Input",
    "output": "~/Documents/Claude Code/Output",
    "procesados": "~/Documents/Claude Code/Procesados",
    "vault_obsidian": "~/Documents/Obsidian/Mi Vault",
    "transcriptotem": "~/Documents/Transcriptotem_WebApp_v2",
}

DEFAULT_FECHA_INICIO = "2026-08-03"


def preguntar(mensaje: str, default: str) -> str:
    respuesta = input(f"{mensaje} [{default}]: ").strip()
    return respuesta if respuesta else default


def preguntar_ruta(mensaje: str, default: str) -> Path:
    while True:
        cruda = preguntar(mensaje, default)
        ruta = Path(cruda).expanduser().resolve()
        return ruta


def preguntar_fecha(mensaje: str, default: str) -> str:
    while True:
        cruda = preguntar(mensaje, default)
        try:
            fecha = datetime.strptime(cruda, "%Y-%m-%d")
        except ValueError:
            print("Formato invalido. Usa AAAA-MM-DD, por ejemplo 2026-08-03.")
            continue
        if fecha.weekday() != 0:
            print(
                f"Ojo: {cruda} no es un lunes (es "
                f"{['lunes','martes','miercoles','jueves','viernes','sabado','domingo'][fecha.weekday()]}). "
                "El calculo de semana de clase asume que el semestre parte un lunes."
            )
            confirmar = input("Usar igual esta fecha? (s/n) [n]: ").strip().lower()
            if confirmar != "s":
                continue
        return cruda


def preguntar_perfil_whisper(mensaje: str, default: str) -> str:
    opciones = ", ".join(PERFILES_WHISPER_VALIDOS)
    while True:
        respuesta = preguntar(f"{mensaje} (opciones: {opciones})", default)
        if respuesta in PERFILES_WHISPER_VALIDOS:
            return respuesta
        print(f"Perfil no reconocido. Elige uno de: {opciones}")


def main():
    existente = cargar_config() if CONFIG_PATH.exists() else {}
    rutas_existentes = existente.get("rutas", {})
    semestre_existente = existente.get("semestre", {})
    ramos_existentes = existente.get("ramos", {})

    print("Configuracion del orquestador de estudio")
    print("Presiona Enter en cualquier pregunta para aceptar el valor entre corchetes.\n")

    print("--- Carpetas ---")
    input_dir = preguntar_ruta(
        "Carpeta Input (donde dejas las grabaciones)",
        rutas_existentes.get("input", DEFAULTS_RUTAS["input"]),
    )
    output_dir = preguntar_ruta(
        "Carpeta Output (donde quedan los .docx)",
        rutas_existentes.get("output", DEFAULTS_RUTAS["output"]),
    )
    procesados_dir = preguntar_ruta(
        "Carpeta Procesados (donde quedan los audios ya procesados)",
        rutas_existentes.get("procesados", DEFAULTS_RUTAS["procesados"]),
    )

    print("\n--- Vault de Obsidian ---")
    vault_dir = preguntar_ruta(
        "Ruta del vault de Obsidian",
        rutas_existentes.get("vault_obsidian", DEFAULTS_RUTAS["vault_obsidian"]),
    )
    if not vault_dir.exists():
        print(f"Aviso: no encontre esa carpeta ({vault_dir}). Revisa la ruta mas tarde si hace falta.")

    print("\n--- Transcriptotem ---")
    transcriptotem_dir = preguntar_ruta(
        "Ruta de Transcriptotem",
        rutas_existentes.get("transcriptotem", DEFAULTS_RUTAS["transcriptotem"]),
    )
    if not (transcriptotem_dir / "backend" / "transcriber.py").exists():
        print(
            f"Aviso: no encontre backend/transcriber.py dentro de {transcriptotem_dir}. "
            "Revisa la ruta mas tarde si hace falta."
        )

    print("\n--- Semestre ---")
    fecha_inicio = preguntar_fecha(
        "Fecha de inicio del semestre (lunes de la primera semana)",
        semestre_existente.get("fecha_inicio", DEFAULT_FECHA_INICIO),
    )

    print("\n--- Ramos por dia de la semana ---")
    ramos = {}
    for dia in DIAS_SEMANA:
        existente_dia = ramos_existentes.get(dia, {})
        nombre_default = existente_dia.get("nombre", RAMOS_POR_DEFECTO[dia])
        perfil_default = existente_dia.get("perfil_whisper", "es-chile")
        nombre = preguntar(f"Ramo del dia {dia}", nombre_default)
        perfil = preguntar_perfil_whisper(f"Perfil de Whisper para {nombre}", perfil_default)
        ramos[dia] = {"nombre": nombre, "perfil_whisper": perfil}

    for carpeta in (input_dir, output_dir, procesados_dir):
        carpeta.mkdir(parents=True, exist_ok=True)

    config = {
        "rutas": {
            "input": str(input_dir),
            "output": str(output_dir),
            "procesados": str(procesados_dir),
            "vault_obsidian": str(vault_dir),
            "transcriptotem": str(transcriptotem_dir),
        },
        "semestre": {
            "fecha_inicio": fecha_inicio,
        },
        "ramos": ramos,
    }
    guardar_config(config)

    print(f"\nListo. Configuracion guardada en {CONFIG_PATH}")
    print(f"Carpetas creadas: {input_dir}, {output_dir}, {procesados_dir}")


if __name__ == "__main__":
    main()

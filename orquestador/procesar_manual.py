"""
Procesa a mano una grabacion que no pasa por el flujo automatico de Input
(deteccion por dia de la semana). Sirve para audios que no son de un ramo de
horario fijo (una clase de recuperacion en otro dia, una charla, un ramo de
un semestre anterior, etc.), y tambien como forma de probar el pipeline
completo con un audio real sin tener que fingir fechas de archivo ni pasar
por la carpeta Input.

Corre la misma cadena que el flujo automatico (transcribir -> skill ->
conceptos repetidos -> docx -> archivado -> Anki -> notificacion). La unica
diferencia es que el ramo se da a mano en vez de resolverse por el dia de
la semana. Acepta una o varias partes de audio (se ordenan por fecha de
modificacion, igual que en el flujo automatico, y se concatenan en ese orden).

Ojo: los audios originales se MUEVEN (no se copian) a Procesados/[Ramo]/ al
terminar, igual que en el flujo automatico.

Uso: python3 -m orquestador.procesar_manual <ramo> [perfil_whisper] -- <ruta_audio1> [ruta_audio2 ...]
"""
import sys
from datetime import date
from pathlib import Path

import anyio

from . import lock
from .config import PERFILES_WHISPER_VALIDOS, cargar_config
from .deteccion import NOMBRES_DIA
from .finalizar_clase import procesar_clase_reconocida
from .nombres import calcular_numero_clase_por_orden, slug_pendiente
from .transcripcion import PENDIENTES_DIR, _guardar_pendiente, transcribir_trabajo

PERFIL_WHISPER_POR_DEFECTO = "es-chile"


def _construir_trabajo_manual(
    rutas_audio: list[Path], ramo: str, perfil_whisper: str, config: dict
) -> dict:
    rutas_en_orden = sorted(rutas_audio, key=lambda p: p.stat().st_mtime)
    fecha = date.fromtimestamp(rutas_en_orden[0].stat().st_mtime)
    nombres = ",".join(p.name for p in rutas_en_orden)
    return {
        "clave": f"manual|{fecha.isoformat()}|{nombres}",
        "fecha": fecha.isoformat(),
        "dia_semana": NOMBRES_DIA[fecha.weekday()],
        "archivos": [str(p) for p in rutas_en_orden],
        "reconocido": True,
        "ramo": ramo,
        "perfil_whisper": perfil_whisper,
        "numero_clase": calcular_numero_clase_por_orden(
            Path(config["rutas"]["procesados"]), ramo, fecha
        ),
        "numeracion": "orden",
    }


async def procesar_grabacion_manual(
    rutas_audio: list[str], ramo: str, perfil_whisper: str = PERFIL_WHISPER_POR_DEFECTO
) -> Path:
    rutas_audio_path = [Path(r).expanduser().resolve() for r in rutas_audio]
    for ruta in rutas_audio_path:
        if not ruta.is_file():
            raise FileNotFoundError(f"No encontre el archivo de audio: {ruta}")

    print("Esperando el candado (por si el ciclo automatico esta corriendo ahora mismo)...")
    lock_file = lock.adquirir_bloqueante()
    try:
        config = cargar_config()
        trabajo = _construir_trabajo_manual(rutas_audio_path, ramo, perfil_whisper, config)

        print(f"Transcribiendo {len(rutas_audio_path)} archivo(s) (ramo: {ramo})...")
        texto = transcribir_trabajo(trabajo, config)
        _guardar_pendiente(trabajo, texto)

        slug = slug_pendiente(trabajo["clave"])
        trabajo_metadata = dict(trabajo)
        trabajo_metadata["archivos_originales"] = trabajo_metadata.pop("archivos")
        trabajo_metadata["archivo_texto"] = str(PENDIENTES_DIR / f"{slug}.txt")
        trabajo_metadata["slug"] = slug

        return await procesar_clase_reconocida(trabajo_metadata, config)
    finally:
        lock.liberar(lock_file)


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 2:
        print(
            "Uso: python3 -m orquestador.procesar_manual <ramo> [perfil_whisper] -- "
            "<ruta_audio1> [ruta_audio2 ...]"
        )
        raise SystemExit(1)

    ramo = args[0]
    resto = args[1:]
    if resto and resto[0] in PERFILES_WHISPER_VALIDOS:
        perfil = resto[0]
        rutas = resto[1:]
    else:
        perfil = PERFIL_WHISPER_POR_DEFECTO
        rutas = resto
    rutas = [r for r in rutas if r != "--"]

    if not rutas:
        print("Falta indicar al menos una ruta de audio.")
        raise SystemExit(1)

    ruta_docx = anyio.run(procesar_grabacion_manual, rutas, ramo, perfil)
    print(f"Listo: {ruta_docx}")

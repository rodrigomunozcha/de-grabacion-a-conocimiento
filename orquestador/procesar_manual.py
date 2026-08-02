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

from . import estado_vivo, lock
from .config import PERFILES_WHISPER_VALIDOS, cargar_config, dir_pendientes
from .deteccion import NOMBRES_DIA
from .finalizar_clase import procesar_clase_reconocida
from .nombres import calcular_numero_clase_por_orden, slug_pendiente
from .transcripcion import _guardar_pendiente, transcribir_trabajo

PERFIL_WHISPER_POR_DEFECTO = "es-chile"


def _construir_trabajo_manual(
    rutas_audio: list[Path], ramo: str, perfil_whisper: str, config: dict,
    fecha_forzada: date | None = None,
) -> dict:
    """
    `fecha_forzada` existe para las grabaciones antiguas con la fecha de
    archivo corrupta. Pasar por AirDrop o por varias copias puede dejar el
    mtime en 1970, y ese mtime es lo unico que hay para fechar la clase. Como
    la fecha es el identificador permanente (va en el nombre del archivo y en
    el titulo de la nota), conviene poder darla a mano en vez de archivar la
    clase con una fecha que se sabe falsa.
    """
    rutas_en_orden = sorted(rutas_audio, key=lambda p: p.stat().st_mtime)
    fecha = fecha_forzada or date.fromtimestamp(rutas_en_orden[0].stat().st_mtime)
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
    rutas_audio: list[str], ramo: str, perfil_whisper: str = PERFIL_WHISPER_POR_DEFECTO,
    fecha: str | None = None,
) -> Path:
    rutas_audio_path = [Path(r).expanduser().resolve() for r in rutas_audio]
    for ruta in rutas_audio_path:
        if not ruta.is_file():
            raise FileNotFoundError(f"No encontre el archivo de audio: {ruta}")

    print("Esperando el candado (por si el ciclo automatico esta corriendo ahora mismo)...")
    lock_file = lock.adquirir_bloqueante()
    try:
        config = cargar_config()
        estado_vivo.iniciar(f"{ramo}")
        estado_vivo.lanzar_visor()
        trabajo = _construir_trabajo_manual(
            rutas_audio_path, ramo, perfil_whisper, config,
            date.fromisoformat(fecha) if fecha else None,
        )

        print(f"Transcribiendo {len(rutas_audio_path)} archivo(s) (ramo: {ramo})...")
        texto = transcribir_trabajo(trabajo, config)
        _guardar_pendiente(trabajo, texto)

        slug = slug_pendiente(trabajo["clave"])
        trabajo_metadata = dict(trabajo)
        trabajo_metadata["archivos_originales"] = trabajo_metadata.pop("archivos")
        trabajo_metadata["archivo_texto"] = str(dir_pendientes() / f"{slug}.txt")
        trabajo_metadata["slug"] = slug

        ruta_docx = await procesar_clase_reconocida(trabajo_metadata, config)
        estado_vivo.terminar("Listo, revisa la carpeta Output")
        return ruta_docx
    except Exception:
        estado_vivo.terminar("El procesamiento se interrumpió", error=True)
        raise
    finally:
        lock.liberar(lock_file)


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 2:
        print(
            "Uso: python3 -m orquestador.procesar_manual <ramo> [perfil_whisper] "
            "[--fecha AAAA-MM-DD] -- <ruta_audio1> [ruta_audio2 ...]"
        )
        raise SystemExit(1)

    # --fecha para grabaciones antiguas cuyo mtime quedo corrupto (ver
    # _construir_trabajo_manual).
    fecha_manual = None
    if "--fecha" in args:
        i = args.index("--fecha")
        try:
            fecha_manual = args[i + 1]
            date.fromisoformat(fecha_manual)
        except (IndexError, ValueError):
            print("--fecha necesita una fecha valida en formato AAAA-MM-DD.")
            raise SystemExit(1)
        args = args[:i] + args[i + 2:]

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

    ruta_docx = anyio.run(procesar_grabacion_manual, rutas, ramo, perfil, fecha_manual)
    print(f"Listo: {ruta_docx}")

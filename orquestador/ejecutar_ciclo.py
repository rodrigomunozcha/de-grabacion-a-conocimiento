"""
Un ciclo completo del orquestador: escanea Input, transcribe lo que ya este
estable, y termina de procesar (skill, conceptos repetidos, docx, archivado,
Anki, notificacion) lo que ya haya sido transcrito. Pensado para correr cada
20-30 segundos via el agente de launchd (ver el .plist en esta carpeta).

Usa un lock de archivo para evitar que dos ciclos corran al mismo tiempo si
uno tarda mas que el intervalo entre invocaciones de launchd (por ejemplo si
la skill esta tardando varios minutos, no queremos una transcripcion nueva
arrancando en paralelo y compitiendo por CPU/GPU del M3).
"""
import anyio

from . import lock
from .config import cargar_config
from .finalizar_clase import procesar_pendientes_reconocidos
from .transcripcion import procesar_pendientes


async def _ciclo_async(config: dict) -> None:
    procesar_pendientes(config)
    await procesar_pendientes_reconocidos(config)


def main() -> None:
    lock_file = lock.adquirir_no_bloqueante()
    if lock_file is None:
        print("Ya hay un ciclo o un procesamiento manual corriendo, salgo sin hacer nada.")
        return

    try:
        config = cargar_config()
        anyio.run(_ciclo_async, config)
    finally:
        lock.liberar(lock_file)


if __name__ == "__main__":
    main()

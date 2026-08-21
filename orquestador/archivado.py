"""
Etapa 6 (parte 1): archiva el audio original de una clase ya procesada, en
Procesados/[Ramo]/, con el nombre compartido de la clase (ver nombres.py).
Si la clase tiene varias partes, cada archivo conserva su propia extension
y se numera para no pisarse entre si.

Una vez movido, se intenta comprimir a AAC en el mismo lugar (ver
comprimir_notas_voz.comprimir_en_sitio). La clase ya paso por Whisper, que
igual reduce todo a 16 kHz mono antes de transcribir (el porque, con las
funciones exactas que lo hacen, esta en el encabezado de
comprimir_notas_voz.py), asi que conservar el audio original sin comprimir en
Procesados/ solo gasta espacio sin proteger nada. Si la compresion falla o
ffmpeg no esta, el audio se archiva igual sin comprimir: no vale la pena
perder una clase por esto.

El original que se reemplaza NUNCA se borra: comprimir_en_sitio lo mueve a
"Grabaciones ya procesadas y por borrar/[Ramo]/", para que el estudiante lo
borre el mismo cuando quiera. Este pipeline no borra archivos por su cuenta.
"""
import shutil
from pathlib import Path

from .comprimir_notas_voz import comprimir_en_sitio
from .ensayo import es_ensayo
from .nombres import nombre_base


def archivar_audio(trabajo: dict, titulo: str, config: dict, bitacora=None) -> list[Path]:
    ramo = trabajo["ramo"]
    procesados_dir = Path(config["rutas"]["procesados"]) / ramo
    procesados_dir.mkdir(parents=True, exist_ok=True)

    base = nombre_base(trabajo["numero_clase"], trabajo["fecha"], titulo)
    archivos = [Path(a) for a in trabajo["archivos"]]
    # En un ensayo el audio "original" suele ser material real ya archivado:
    # moverlo lo sacaria de su lugar de verdad. Se copia, y se toleran los que
    # ya no esten donde decia la metadata (ver ensayo.py).
    ensayo = es_ensayo(config)

    destinos = []
    for i, origen in enumerate(archivos, start=1):
        sufijo = f" (parte {i})" if len(archivos) > 1 else ""
        destino = procesados_dir / f"{base}{sufijo}{origen.suffix}"
        if ensayo:
            if not origen.is_file():
                continue
            shutil.copy2(str(origen), str(destino))
        else:
            # Se anota ANTES de mover: si el corte llega justo despues del
            # movimiento pero antes de anotarlo, el audio quedaria fuera de
            # su sitio sin nada que lo devuelva.
            if bitacora is not None:
                bitacora.audio_movido(origen, destino)
            shutil.move(str(origen), str(destino))
            comprimir_en_sitio(destino)
        destinos.append(destino)
    return destinos

"""
Etapa 6 (parte 1): archiva el audio original de una clase ya procesada, en
Procesados/[Ramo]/, con el nombre compartido de la clase (ver nombres.py).
Si la clase tiene varias partes, cada archivo conserva su propia extension
y se numera para no pisarse entre si.
"""
import shutil
from pathlib import Path

from .ensayo import es_ensayo
from .nombres import nombre_base


def archivar_audio(trabajo: dict, titulo: str, config: dict) -> list[Path]:
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
            shutil.move(str(origen), str(destino))
        destinos.append(destino)
    return destinos

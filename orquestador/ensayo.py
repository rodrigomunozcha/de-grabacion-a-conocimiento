"""
Modo ensayo: corre el pipeline completo de verdad, pero contra un sandbox
desechable, sin tocar nada real.

Por que existe. Probar un cambio en el pipeline significaba correrlo contra el
vault real, el Anki real y los audios reales. Eso deja notas de prueba
mezcladas con las de estudio, tarjetas basura en los mazos, y sobre todo
MUEVE el audio original (archivado.py usa shutil.move, no copia). O sea, la
unica forma de saber si un cambio funcionaba era arriesgar el material real,
que es justo lo que no se puede perder. Terminabas eligiendo entre probar o
estar seguro.

Como funciona. No hay una version "de mentira" del pipeline: se corre el
mismo codigo, con la misma skill y el mismo revisor. Lo unico que cambia es
la configuracion que recibe: todas las rutas de escritura apuntan a una
carpeta temporal, y las dos acciones que no son rutas (agregar a Anki y mover
el audio original) consultan la marca `modo_ensayo` y se comportan distinto.
Asi el ensayo no puede desviarse del comportamiento real por accidente: si
manana alguien agrega una etapa nueva que escribe en el vault, ya queda
cubierta, porque escribe en la ruta que le paso la configuracion.

Que se protege, concretamente:
  - el vault de Obsidian (las notas van a un vault de mentira)
  - Anki (no se agrega ninguna tarjeta, solo se informa cuantas habrian sido)
  - el audio original (se copia en vez de moverse)
  - config.json (el cache de carpetas del ensayo no se guarda)
  - Output/ y Procesados/ (van al sandbox)
  - transcripciones_pendientes/ (los intermedios van al sandbox)

Ese ultimo es el menos obvio y el mas peligroso de los seis. Un ensayo escribe
<slug>_skill.json, que es justamente la marca de "esta clase ya se proceso". Si
esa marca quedara en la carpeta real, la siguiente corrida de verdad se saltaria
la clase en silencio: sin notas, sin .docx y sin ningun error que lo delate.

Uso:
    python3 -m orquestador.ensayo                      # lista que se puede ensayar
    python3 -m orquestador.ensayo <slug>               # ensaya esa transcripcion
    python3 -m orquestador.ensayo <slug> --conservar   # no borra el sandbox al final
"""
import copy
import shutil
import tempfile
from pathlib import Path

from .config import PENDIENTES_DIR_POR_DEFECTO, usar_dir_pendientes

CLAVE = "modo_ensayo"

# Carpetas que no aportan al ensayo y si cuestan tiempo de recorrer.
IGNORADAS_AL_REPLICAR = {".obsidian", ".trash", ".git", ".stfolder", "node_modules"}


def es_ensayo(config: dict) -> bool:
    """Unica forma correcta de preguntar si estamos en un ensayo. Las etapas
    que hacen algo irreversible (Anki, mover el audio) deben consultarla."""
    return bool(config.get(CLAVE))


def _replicar_estructura_vault(vault_real: Path, vault_ensayo: Path) -> int:
    """
    Copia solo el ARBOL DE CARPETAS del vault real, sin una sola nota.

    Hace falta porque carpetas.py resuelve donde va cada ramo recorriendo el
    vault, y un vault de ensayo vacio haria que esa resolucion se comportara
    distinto que en la realidad (crearia la carpeta en la raiz en vez de
    encontrarla donde de verdad esta). Con la estructura replicada, el ensayo
    ejercita el mismo camino que una corrida real. Sin notas adentro, no hay
    forma de confundir una nota de ensayo con una de estudio.
    """
    if not vault_real.is_dir():
        return 0
    creadas = 0
    for ruta in vault_real.rglob("*"):
        if not ruta.is_dir():
            continue
        if any(p in IGNORADAS_AL_REPLICAR or p.startswith(".") for p in ruta.parts):
            continue
        (vault_ensayo / ruta.relative_to(vault_real)).mkdir(parents=True, exist_ok=True)
        creadas += 1
    return creadas


def preparar(config: dict, carpeta_base: Path | None = None) -> tuple[dict, Path]:
    """
    Devuelve (config_de_ensayo, carpeta_sandbox).

    El config original no se modifica: se trabaja sobre una copia, para que
    quien llame pueda seguir usando el real si lo necesita.
    """
    sandbox = Path(carpeta_base) if carpeta_base else Path(tempfile.mkdtemp(prefix="ensayo_"))
    sandbox.mkdir(parents=True, exist_ok=True)

    ensayo = copy.deepcopy(config)
    vault_real = Path(config["rutas"]["vault_obsidian"]).expanduser()
    vault_ensayo = sandbox / "vault"

    for nombre in ("input", "output", "procesados"):
        destino = sandbox / nombre
        destino.mkdir(parents=True, exist_ok=True)
        ensayo["rutas"][nombre] = str(destino)
    ensayo["rutas"]["vault_obsidian"] = str(vault_ensayo)

    _replicar_estructura_vault(vault_real, vault_ensayo)

    # El cache de carpetas apunta a rutas del vault real. Dentro del ensayo no
    # sirven y ademas serian una via para escribir donde no corresponde.
    ensayo["carpetas_ramo"] = {}
    ensayo[CLAVE] = True

    # Los intermedios (<slug>_skill.json, <slug>_revision.json) tambien al
    # sandbox: ver el encabezado de este modulo para por que importa tanto.
    pendientes_ensayo = sandbox / "pendientes"
    pendientes_ensayo.mkdir(parents=True, exist_ok=True)
    usar_dir_pendientes(pendientes_ensayo)

    return ensayo, sandbox


def _resumen(sandbox: Path) -> None:
    vault = sandbox / "vault"
    notas = sorted(vault.rglob("*.md"))
    docx = sorted((sandbox / "output").rglob("*.docx"))
    audios = sorted((sandbox / "procesados").rglob("*"))

    print("\n" + "=" * 62)
    print("RESULTADO DEL ENSAYO")
    print("=" * 62)

    print(f"\nNotas escritas en el vault de ensayo ({len(notas)}):")
    for n in notas:
        print(f"  - {n.relative_to(vault)}  ({n.stat().st_size:,} bytes)")

    print(f"\nDocumentos .docx generados ({len(docx)}):")
    for d in docx:
        print(f"  - {d.name}  ({d.stat().st_size:,} bytes)")

    audios_archivos = [a for a in audios if a.is_file()]
    print(f"\nAudios archivados, copiados no movidos ({len(audios_archivos)}):")
    for a in audios_archivos:
        print(f"  - {a.name}")

    print(f"\nTodo lo anterior esta en:\n  {sandbox}")


def _listar_ensayables() -> list[tuple[str, Path]]:
    if not PENDIENTES_DIR_POR_DEFECTO.exists():
        return []
    return [
        (p.stem, p)
        for p in sorted(PENDIENTES_DIR_POR_DEFECTO.glob("*.json"))
        if not p.stem.endswith(("_skill", "_revision"))
    ]


async def ensayar(slug: str, conservar: bool = False) -> Path:
    """Corre el pipeline completo sobre una transcripcion ya guardada."""
    import json

    from .config import cargar_config
    from .finalizar_clase import procesar_clase_reconocida

    ruta_metadata = PENDIENTES_DIR_POR_DEFECTO / f"{slug}.json"
    if not ruta_metadata.is_file():
        disponibles = ", ".join(s for s, _ in _listar_ensayables()) or "ninguna"
        raise FileNotFoundError(
            f"No existe {ruta_metadata.name}. Transcripciones disponibles: {disponibles}"
        )

    trabajo_metadata = json.loads(ruta_metadata.read_text(encoding="utf-8"))
    config_ensayo, sandbox = preparar(cargar_config())

    print(f"Ensayando: {trabajo_metadata.get('ramo')} - {trabajo_metadata.get('fecha')}")
    print(f"Sandbox  : {sandbox}")
    print("Nada de esto toca tu vault, tu Anki ni tus audios.\n")

    try:
        await procesar_clase_reconocida(trabajo_metadata, config_ensayo)
        _resumen(sandbox)
    finally:
        usar_dir_pendientes(None)
        if not conservar:
            print("\n(El sandbox se borra al terminar. Usa --conservar para revisarlo.)")
            shutil.rmtree(sandbox, ignore_errors=True)
    return sandbox


if __name__ == "__main__":
    import sys

    import anyio

    args = [a for a in sys.argv[1:]]
    conservar = "--conservar" in args
    args = [a for a in args if not a.startswith("--")]

    if not args:
        print("Transcripciones que se pueden ensayar:\n")
        for slug, ruta in _listar_ensayables():
            import json as _json

            meta = _json.loads(ruta.read_text(encoding="utf-8"))
            print(f"  {slug}")
            print(f"      {meta.get('ramo')} - {meta.get('fecha')}")
        print("\nUso: python3 -m orquestador.ensayo <slug> [--conservar]")
        raise SystemExit(0)

    anyio.run(ensayar, args[0], conservar)

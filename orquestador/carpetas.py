"""
Resuelve en que carpeta del vault van las notas de un ramo, del lado de
Python, para que la skill no tenga que salir a buscarla.

Por que existe. Antes el prompt le pasaba a la skill la raiz del vault y el
nombre del ramo, y ella tenia que ubicar la carpeta con Glob y Grep. Eso
significa listar un vault entero (322 notas repartidas en 77 carpetas, con
rutas largas) y dejar ese listado en el contexto, que despues se relee en
cada turno. Fue lo que obligo a subir MAX_TURNS de 40 a 80 en su momento
(ver skill_runner.py).

Buscar una carpeta es trabajo predecible: no requiere criterio, requiere
comparar strings. O sea es exactamente lo que no deberia estar haciendo un
modelo. Aca se hace una vez, se guarda la ruta en config.json bajo
"carpetas_ramo", y a partir de la segunda clase de ese ramo ni siquiera se
recorre el vault.

Donde se crea un ramo nuevo: al lado de los que ya existen. Si ya hay al
menos una carpeta de ramo resuelta, la nueva va como hermana de esa, porque
esa es la estructura que el estudiante ya eligio (en su vault los ramos
cuelgan de una carpeta de la carrera, varios niveles adentro). Solo si no
hay ninguna referencia se cae a la raiz del vault.
"""
import unicodedata
from pathlib import Path

# Carpetas internas del vault y ruido del sistema. Recorrerlas no aporta y
# ".obsidian" en particular tiene cientos de archivos de configuracion.
IGNORADAS = {".obsidian", ".trash", ".git", ".stfolder", "node_modules"}


def _normalizar(nombre: str) -> str:
    """Para comparar nombres de carpeta sin que un acento o una mayuscula
    hagan fallar la coincidencia. El ramo se escribe a mano en el setup y no
    siempre queda identico al nombre de la carpeta del vault."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", nombre)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.lower().split())


def buscar_carpeta(vault_dir: str | Path, ramo: str) -> Path | None:
    """Primera carpeta del vault cuyo nombre coincide con el ramo. None si no
    hay ninguna."""
    raiz = Path(vault_dir).expanduser()
    if not raiz.is_dir():
        return None

    objetivo = _normalizar(ramo)
    candidatas = []
    for ruta in raiz.rglob("*"):
        if not ruta.is_dir():
            continue
        if any(parte in IGNORADAS or parte.startswith(".") for parte in ruta.parts):
            continue
        if _normalizar(ruta.name) == objetivo:
            candidatas.append(ruta)

    if not candidatas:
        return None
    # La menos profunda: si por lo que sea hay una copia anidada, gana la que
    # esta mas arriba en el arbol.
    return min(candidatas, key=lambda p: len(p.parts))


def _carpeta_padre_para_ramo_nuevo(vault_dir: str | Path, config: dict) -> Path:
    """Donde colgar un ramo que todavia no tiene carpeta: junto a los ramos que
    ya existen, si los hay."""
    for ruta in (config.get("carpetas_ramo") or {}).values():
        candidata = Path(ruta).expanduser()
        if candidata.is_dir():
            return candidata.parent
    return Path(vault_dir).expanduser()


def resolver_carpeta_ramo(ramo: str, vault_dir: str, config: dict) -> tuple[Path, bool]:
    """
    Devuelve (carpeta, config_cambio).

    La carpeta existe siempre al volver de aqui: si no estaba, se crea. Asi la
    skill recibe una ruta lista para escribir y no tiene que decidir nada sobre
    el sistema de archivos.

    El segundo valor avisa si hubo que anotar algo nuevo en config.json, para
    que quien llama lo guarde. No se guarda aqui adentro para no escribir la
    configuracion desde una funcion que en teoria solo resuelve una ruta.
    """
    cache = config.setdefault("carpetas_ramo", {})

    guardada = cache.get(ramo)
    if guardada:
        carpeta = Path(guardada).expanduser()
        if carpeta.is_dir():
            return carpeta, False
        # La ruta guardada ya no existe (el estudiante reordeno el vault o
        # cambio de vault). Se descarta y se resuelve de nuevo.

    encontrada = buscar_carpeta(vault_dir, ramo)
    if encontrada is None:
        encontrada = _carpeta_padre_para_ramo_nuevo(vault_dir, config) / ramo
        encontrada.mkdir(parents=True, exist_ok=True)

    cache[ramo] = str(encontrada)
    return encontrada, True


if __name__ == "__main__":
    import sys

    from .config import cargar_config

    if len(sys.argv) != 2:
        print("Uso: python3 -m orquestador.carpetas <nombre del ramo>")
        raise SystemExit(1)

    config = cargar_config()
    carpeta, cambio = resolver_carpeta_ramo(
        sys.argv[1], config["rutas"]["vault_obsidian"], config
    )
    print(carpeta)
    print("(nueva en el cache)" if cambio else "(ya estaba en el cache)")

"""
Motor de deteccion y agrupacion de grabaciones en Input.

Se asume que este modulo se llama cada vez que el estudiante hace clic en la app
"Procesar clases" (ver boton_procesar/). Cada llamada es un "scan": lee el
tamano actual de los archivos en Input, lo compara contra el tamano visto
en el scan anterior (guardado en disco, no en memoria, porque cada clic es
un proceso nuevo), y considera "estable" un archivo cuyo tamano no cambio
entre dos scans seguidos.

Nota sobre la fecha de referencia: se usa la fecha de MODIFICACION
(mtime) del archivo, no la de creacion (birthtime). El estudiante pasa los
audios por AirDrop al escritorio y de ahi a Input. El mtime refleja
cuando termino de grabarse el audio y sobrevive copias y AirDrop de
forma mas confiable que el birthtime, que en varios sistemas de
archivos se resetea al momento de la copia.
"""
import json
import re
from datetime import date, datetime
from pathlib import Path

from .config import cargar_config, DIAS_SEMANA

EXTENSIONES_AUDIO = {".m4a", ".mp3", ".wav"}

ESTADO_TAMANOS_PATH = Path(__file__).parent / "estado_tamanos.json"
TRABAJOS_EMITIDOS_PATH = Path(__file__).parent / "trabajos_emitidos.json"

NOMBRES_DIA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

# Algunas grabaciones (vistas en vivo con clases de un ramo de intercambio)
# llegan con la fecha de modificacion corrupta, agrupada cerca del inicio de
# la era Unix (1970). Cualquier fecha asi de vieja no puede ser real para una
# grabacion de clase, asi que se intenta rescatar la fecha real del nombre
# del archivo (algunas grabaciones usan el patron DD.MM.YY en el nombre, ej.
# "Curso101 10.04.25 Clase 5").
FECHA_MINIMA_PLAUSIBLE = date(2000, 1, 1)
PATRON_FECHA_EN_NOMBRE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b")


def _extraer_fecha_de_nombre(nombre: str) -> date | None:
    m = PATRON_FECHA_EN_NOMBRE.search(nombre)
    if not m:
        return None
    dia, mes, anio = (int(x) for x in m.groups())
    if anio < 100:
        anio += 2000
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def _resolver_fecha_archivo(archivo: Path) -> date:
    fecha_mtime = date.fromtimestamp(archivo.stat().st_mtime)
    if fecha_mtime >= FECHA_MINIMA_PLAUSIBLE:
        return fecha_mtime
    return _extraer_fecha_de_nombre(archivo.name) or fecha_mtime


def _cargar_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _guardar_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def listar_audios(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        return []
    return sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSIONES_AUDIO
    )


def actualizar_estables(input_dir: Path) -> list[Path]:
    """
    Compara tamanos actuales contra el scan anterior.
    Devuelve los archivos cuyo tamano no cambio entre dos scans seguidos.
    Actualiza el estado guardado en disco con los tamanos de este scan.
    """
    estado_previo = _cargar_json(ESTADO_TAMANOS_PATH)
    estado_nuevo = {}
    estables = []

    for archivo in listar_audios(input_dir):
        clave = str(archivo)
        tamano_actual = archivo.stat().st_size
        estado_nuevo[clave] = tamano_actual
        tamano_previo = estado_previo.get(clave)
        if tamano_previo is not None and tamano_previo == tamano_actual:
            estables.append(archivo)

    # Limpia del estado los archivos que ya no estan en Input (se movieron o borraron)
    _guardar_json(ESTADO_TAMANOS_PATH, estado_nuevo)
    return estables


def agrupar_por_fecha(archivos: list[Path]) -> dict[date, list[Path]]:
    grupos: dict[date, list[Path]] = {}
    for archivo in archivos:
        fecha = _resolver_fecha_archivo(archivo)
        grupos.setdefault(fecha, []).append(archivo)
    return grupos


def resolver_ramo(fecha: date, config: dict) -> dict | None:
    inicio_semestre = datetime.strptime(config["semestre"]["fecha_inicio"], "%Y-%m-%d").date()
    if fecha < inicio_semestre:
        # Fecha de archivo poco confiable (ej. metadata corrupta en 1970 por
        # una transferencia que no preservo la fecha real). Aunque el dia de
        # semana coincida por casualidad con un ramo actual, no lo asumas:
        # que dispare el dialogo de dia no reconocido en vez de asignar mal.
        return None
    dia_semana = NOMBRES_DIA[fecha.weekday()]
    if dia_semana not in DIAS_SEMANA:
        return None
    return config["ramos"].get(dia_semana)


def calcular_semana_semestre(fecha: date, fecha_inicio_semestre: str) -> int:
    inicio = datetime.strptime(fecha_inicio_semestre, "%Y-%m-%d").date()
    return ((fecha - inicio).days // 7) + 1


def _clave_trabajo(fecha: date, archivos: list[Path]) -> str:
    nombres = ",".join(sorted(a.name for a in archivos))
    return f"{fecha.isoformat()}|{nombres}"


def construir_trabajos(config: dict | None = None) -> list[dict]:
    """
    Funcion principal de esta etapa. Devuelve la lista de trabajos listos
    para procesar: grupos de archivos estables, agrupados por dia, con el
    ramo y la semana ya resueltos (o marcados como no reconocidos).

    No repite un trabajo que ya fue emitido antes (ver marcar_emitido).
    """
    if config is None:
        config = cargar_config()

    input_dir = Path(config["rutas"]["input"])
    emitidos = _cargar_json(TRABAJOS_EMITIDOS_PATH)

    estables = actualizar_estables(input_dir)
    grupos = agrupar_por_fecha(estables)

    trabajos = []
    for fecha, archivos in sorted(grupos.items()):
        clave = _clave_trabajo(fecha, archivos)
        if clave in emitidos:
            continue
        archivos_en_orden = sorted(archivos, key=lambda p: p.stat().st_mtime)
        ramo_info = resolver_ramo(fecha, config)
        trabajo = {
            "clave": clave,
            "fecha": fecha.isoformat(),
            "dia_semana": NOMBRES_DIA[fecha.weekday()],
            "archivos": [str(a) for a in archivos_en_orden],
            "reconocido": ramo_info is not None,
            "ramo": ramo_info["nombre"] if ramo_info else None,
            "perfil_whisper": ramo_info["perfil_whisper"] if ramo_info else None,
            "numero_clase": calcular_semana_semestre(fecha, config["semestre"]["fecha_inicio"]),
            "numeracion": "calendario",
        }
        trabajos.append(trabajo)
    return trabajos


DIAS_RETENCION_EMITIDOS = 180


def _podar_emitidos(emitidos: dict) -> dict:
    """Sin esto, trabajos_emitidos.json crece para siempre. Se guarda solo
    la fecha en que se marco cada uno, asi que podar por antiguedad es
    suficiente (mas simple y confiable que reconstruir rutas completas a
    partir de la clave, que solo guarda nombres de archivo)."""
    limite = datetime.now().timestamp() - DIAS_RETENCION_EMITIDOS * 86400
    resultado = {}
    for clave, marca in emitidos.items():
        try:
            if datetime.fromisoformat(marca).timestamp() >= limite:
                resultado[clave] = marca
        except ValueError:
            continue
    return resultado


def marcar_emitido(trabajo: dict) -> None:
    """
    Marca un trabajo como ya entregado a la siguiente etapa, para que
    construir_trabajos() no lo vuelva a devolver en un proximo scan.
    Se llama cuando ese trabajo ya quedo resuelto de una forma u otra
    (transcrito, ignorado), no antes: asi un fallo a mitad de camino puede
    reintentarse con otro clic en vez de quedar en el limbo para siempre.
    """
    emitidos = _podar_emitidos(_cargar_json(TRABAJOS_EMITIDOS_PATH))
    emitidos[trabajo["clave"]] = datetime.now().isoformat()
    _guardar_json(TRABAJOS_EMITIDOS_PATH, emitidos)


if __name__ == "__main__":
    for t in construir_trabajos():
        print(json.dumps(t, indent=2, ensure_ascii=False))

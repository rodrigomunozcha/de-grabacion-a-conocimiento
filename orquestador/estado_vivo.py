"""
Estado en vivo de la corrida actual, para que algo externo pueda mostrarlo
mientras el pipeline trabaja (hoy lo lee el icono de la barra de menu, ver
barra_menu/).

Por que existe. Hasta ahora la unica forma de saber si algo estaba pasando era
cazar una notificacion al vuelo o abrir Estado.txt a mano. El flujo real es
"suelto la clase y me voy": si a los diez minutos no hay senal, no habia forma
de distinguir entre "va bien, la skill tarda" y "se colgo hace rato".

Contrato con quien lo lee: este modulo solo ESCRIBE un archivo JSON. No lanza
ventanas, no habla con nadie, no espera respuesta. Si el visor se cae, o no
existe, o nadie lo mira, el pipeline no se entera y sigue igual. Esa es la
razon de que sea un archivo y no una conexion: no puede convertirse en un
punto nuevo de rotura.

Sobre las estimaciones. Solo se estima donde hay con que:
  - Transcribir: se calcula desde la duracion real del audio (ffprobe) y una
    velocidad medida en este Mac.
  - Skill y revision: no hay forma de saber cuanto le falta a un modelo. Se usa
    el promedio de las corridas anteriores registradas en logs/uso.jsonl, y si
    todavia no hay historial, no se muestra ningun numero en vez de inventarlo.
"""
import json
import os
import subprocess
import time
from pathlib import Path

ESTADO_PATH = Path(__file__).parent / "estado_actual.json"
USO_PATH = Path(__file__).parent / "logs" / "uso.jsonl"
VISOR_PATH = Path(__file__).parent.parent / "barra_menu" / "BarraEstado"

# Los pasos del pipeline, en orden. El indice es lo que se muestra como
# "Paso N de M". Se declaran aca y se referencian desde cada etapa, para que
# renombrar un paso no desincronice la numeracion.
PASO_TRANSCRIBIR = "Transcribiendo el audio"
PASO_SKILL = "Analizando la clase"
PASO_REVISION = "Revisando lo escrito"
PASO_DOCUMENTO = "Armando el documento y archivando"
PASO_ANKI = "Agregando las flashcards"

PASOS = [PASO_TRANSCRIBIR, PASO_SKILL, PASO_REVISION, PASO_DOCUMENTO, PASO_ANKI]

# Segundos de audio transcritos por segundo de reloj, cuando todavia no hay
# historial propio. Deliberadamente pesimista.
#
# La primera version tenia 20.0, calibrado suponiendo la duracion de un audio
# en vez de medirla. Medido de verdad, ese mismo caso daba 14.5x, y una clase
# distinta corrio a menos de 4.4x con el mismo modelo: Whisper reintenta los
# tramos de poca confianza, asi que una grabacion con peor sonido tarda varias
# veces mas. Una estimacion optimista hace que el icono anuncie que algo "ya
# se paso de lo habitual" mientras en realidad todo va bien, que es peor que
# no estimar nada. Apenas hay una corrida registrada se usa la medicion real
# (ver velocidad_transcripcion).
VELOCIDAD_TRANSCRIPCION_INICIAL = 4.0


def velocidad_transcripcion() -> float:
    """La velocidad mas baja de las ultimas corridas registradas, o la inicial
    si todavia no hay ninguna. Se toma la mas lenta y no el promedio porque
    equivocarse hacia abajo solo hace que termine antes de lo anunciado."""
    if not USO_PATH.exists():
        return VELOCIDAD_TRANSCRIPCION_INICIAL
    velocidades = []
    try:
        for linea in USO_PATH.read_text(encoding="utf-8").splitlines():
            if not linea.strip():
                continue
            d = json.loads(linea)
            if d.get("etapa") == "transcripcion" and d.get("velocidad"):
                velocidades.append(float(d["velocidad"]))
    except Exception:
        return VELOCIDAD_TRANSCRIPCION_INICIAL
    return min(velocidades[-5:]) if velocidades else VELOCIDAD_TRANSCRIPCION_INICIAL


def duracion_audio_segundos(ruta: str | Path) -> float | None:
    """Duracion real del audio con ffprobe. None si no se puede saber."""
    try:
        salida = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(ruta)],
            capture_output=True, text=True, timeout=20,
        )
        return float(salida.stdout.strip())
    except Exception:
        return None


def _promedio_historico(etapa: str) -> float | None:
    """Cuanto tardo esta etapa, en promedio, en las corridas anteriores."""
    if not USO_PATH.exists():
        return None
    duraciones = []
    try:
        for linea in USO_PATH.read_text(encoding="utf-8").splitlines():
            if not linea.strip():
                continue
            d = json.loads(linea)
            if d.get("etapa") == etapa and isinstance(d.get("duracion_s"), (int, float)):
                duraciones.append(float(d["duracion_s"]))
    except Exception:
        return None
    if not duraciones:
        return None
    return sum(duraciones[-10:]) / len(duraciones[-10:])


def lanzar_visor() -> None:
    """
    Abre el icono de la barra de menu, si esta compilado.

    Se lanza suelto y no se espera nada de el: no se guarda el proceso, no se
    revisa que haya arrancado, y cualquier fallo se ignora. El icono es una
    comodidad, no una parte del pipeline, y no puede impedir que una clase se
    procese. Se cierra solo cuando ve activo=False (ver BarraEstado.swift).
    """
    if not VISOR_PATH.is_file():
        return
    try:
        subprocess.Popen(
            [str(VISOR_PATH), str(ESTADO_PATH)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def fijar_proceso(pid: int) -> None:
    """Deja el numero de proceso en el estado, que es lo unico que el icono
    necesita saber para poder pedir el aborto (ver cancelacion.py)."""
    estado = _leer()
    if not estado:
        return
    estado["pid"] = pid
    _escribir(estado)


def fijar_interrumpible(valor: bool) -> None:
    """Le avisa al icono si en este momento se puede abortar. Durante el
    movimiento del audio no se puede, y el boton se muestra en gris con el
    motivo en vez de desaparecer."""
    estado = _leer()
    if not estado:
        return
    estado["interrumpible"] = valor
    _escribir(estado)


def cancelado(detalle: list[str]) -> None:
    """Estado final cuando el estudiante aborto: el icono lo muestra distinto
    de un exito y de un error, porque no es ninguno de los dos."""
    estado = _leer() or {}
    estado.update({"activo": False, "cancelado": True, "fin": time.time(),
                   "resultado": "Se detuvo y se deshizo todo",
                   "revertido": detalle})
    _escribir(estado)


def fijar_clase(nombre: str) -> None:
    """El nombre de la clase se sabe despues de arrancar (hay que resolver el
    ramo primero), asi que se completa aparte."""
    estado = _leer()
    if not estado:
        return
    estado["clase"] = nombre
    _escribir(estado)


def iniciar(clase: str = "") -> None:
    _escribir({
        "activo": True,
        "clase": clase,
        "paso": 0,
        "total": len(PASOS),
        "etapa": "Preparando",
        "detalle": "",
        "inicio": time.time(),
        "inicio_paso": time.time(),
        "eta_segundos": None,
    })


def paso(etapa: str, detalle: str = "", eta_segundos: float | None = None) -> None:
    """Marca en que paso va la corrida. `etapa` deberia ser una de las
    constantes PASO_*; si no esta en la lista, igual se muestra pero sin
    numero de paso."""
    estado = _leer()
    if not estado:
        return
    numero = PASOS.index(etapa) + 1 if etapa in PASOS else estado.get("paso", 0)
    if eta_segundos is None and etapa in (PASO_SKILL, PASO_REVISION):
        eta_segundos = _promedio_historico("destilado" if etapa == PASO_SKILL else "revision")
    estado.update({
        "paso": numero,
        "etapa": etapa,
        "detalle": detalle,
        "inicio_paso": time.time(),
        "eta_segundos": eta_segundos,
    })
    _escribir(estado)


def terminar(resultado: str = "", error: bool = False) -> None:
    """El visor se cierra solo al ver activo=False. Se deja el archivo, en vez
    de borrarlo, para que alcance a mostrar el resultado antes de irse."""
    estado = _leer() or {}
    estado.update({"activo": False, "error": error, "resultado": resultado,
                   "fin": time.time()})
    _escribir(estado)


def limpiar() -> None:
    ESTADO_PATH.unlink(missing_ok=True)


def _leer() -> dict | None:
    try:
        return json.loads(ESTADO_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _escribir(estado: dict) -> None:
    """Escritura atomica: el visor lee este archivo una vez por segundo y no
    puede toparse con un JSON a medio escribir."""
    try:
        tmp = ESTADO_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, ESTADO_PATH)
    except Exception:
        pass  # nunca puede tumbar el pipeline

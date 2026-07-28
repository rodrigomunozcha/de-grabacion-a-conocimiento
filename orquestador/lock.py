"""
Candado compartido para que el ciclo automatico (ejecutar_ciclo.py, via
launchd) y el procesamiento manual (procesar_manual.py) nunca corran al
mismo tiempo. Sin esto, ambos pueden recoger el mismo trabajo pendiente y
procesarlo dos veces en paralelo (visto en vivo: dos títulos distintos para
la misma clase, y un error al final porque un lado ya habia movido el audio
que el otro estaba por transcribir).
"""
import fcntl
from pathlib import Path

LOCK_PATH = Path(__file__).parent / "orquestador.lock"


def adquirir_no_bloqueante():
    """Para el ciclo automatico: si ya hay uno corriendo, no espera, devuelve None."""
    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        return None
    return lock_file


def adquirir_bloqueante():
    """Para uso manual: espera a que el ciclo automatico termine si esta corriendo."""
    lock_file = open(LOCK_PATH, "w")
    fcntl.flock(lock_file, fcntl.LOCK_EX)
    return lock_file


def liberar(lock_file) -> None:
    fcntl.flock(lock_file, fcntl.LOCK_UN)
    lock_file.close()

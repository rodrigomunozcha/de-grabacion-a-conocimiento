"""
Aborto del procesamiento a pedido del estudiante, dejando el disco como estaba.

Como llega la orden. El icono de la barra de menu (ver barra_menu/) manda una
senal al proceso. Aca se atiende esa senal, se deshacen los cambios anotados en
la bitacora y se sale. El icono no sabe nada del pipeline mas alla del numero de
proceso: no le dice que hacer, solo le pide que pare.

Por que hay tramos que no se pueden interrumpir. Casi todo el pipeline se puede
cortar en cualquier momento sin dejar nada roto, porque cada cambio quedo
anotado y se revierte. La excepcion es mover el audio original a Procesados:
ahi el archivo esta a medio camino entre dos carpetas, y cortarlo justo en ese
instante es la unica forma de perderlo. Dura segundos. Durante ese rato el
aborto queda encolado y se aplica apenas termina, y el icono lo muestra en gris
con el motivo, en vez de fingir que el boton no existe.

Limite honesto: la senal se atiende entre instrucciones de Python, asi que si
justo estamos dentro de una llamada larga a codigo nativo (la transcripcion
pasa la mayor parte del tiempo dentro de Whisper), el corte se hace efectivo
cuando esa llamada devuelve el control. En la practica son segundos, porque
Whisper procesa por tramos, pero no es instantaneo.
"""
import os
import signal
import threading

from . import estado_vivo

_bitacora = None
_seccion_critica = threading.Lock()
_pedido_durante_seccion_critica = False


class Abortado(Exception):
    """Se lanza desde el manejador de la senal para desarmar la pila de
    llamadas de forma ordenada, en vez de matar el proceso en seco. Asi los
    bloques finally alcanzan a soltar el candado y cerrar archivos."""


def instalar(bitacora) -> None:
    """Deja el proceso listo para poder abortarse. Se llama una vez, al empezar."""
    global _bitacora
    _bitacora = bitacora
    estado_vivo.fijar_proceso(os.getpid())
    signal.signal(signal.SIGTERM, _al_recibir_senal)
    signal.signal(signal.SIGINT, _al_recibir_senal)


def _al_recibir_senal(signum, frame):
    global _pedido_durante_seccion_critica
    if _seccion_critica.locked():
        # Estamos moviendo el audio. Se anota el pedido y se atiende al salir.
        _pedido_durante_seccion_critica = True
        return
    raise Abortado()


class seccion_critica:
    """
    Marca un tramo que no se puede cortar por la mitad sin arriesgar un archivo.

    Uso:
        with cancelacion.seccion_critica():
            archivar_audio(...)
    """

    def __enter__(self):
        _seccion_critica.acquire()
        estado_vivo.fijar_interrumpible(False)
        return self

    def __exit__(self, *exc):
        global _pedido_durante_seccion_critica
        estado_vivo.fijar_interrumpible(True)
        _seccion_critica.release()
        if _pedido_durante_seccion_critica:
            _pedido_durante_seccion_critica = False
            raise Abortado()
        return False


def deshacer_todo() -> list[str]:
    """Revierte lo que la corrida alcanzo a cambiar. Devuelve que se revirtio."""
    if _bitacora is None:
        return []
    return _bitacora.deshacer()

"""
Comando auxiliar para procesar una grabacion sin pasar por Input, eligiendo el
ramo a mano en dialogos nativos. Sirve para un audio que esta en cualquier
carpeta del Mac, o para forzar un ramo distinto del que el sistema deduciria.

Esto NO es la forma normal de procesar algo que no es una clase. Para eso basta
dejar la grabacion en Input con un nombre que diga de que es: el flujo
automatico lee el ramo del nombre del archivo y, si no reconoce ninguno,
pregunta solo (ver ramo_por_nombre.py). Este modulo quedo como salida de
emergencia para los casos que ese camino no cubre.

Historia, porque explica por que existe teniendo el otro camino: se escribio
primero, como una app de doble clic aparte que preguntaba el ramo siempre. La
idea se descarto - dos apps para el mismo gesto es peor problema que el que
resolvia - y la app se retiro. El modulo se conservo porque el trabajo util ya
estaba hecho y no estorba mientras no tenga icono.

El trabajo pesado vive en procesar_manual.py, que hace lo mismo por linea de
comandos con argumentos. Aca solo se le agrega la capa de dialogos.

Uso: python3 -m orquestador.procesar_aparte [ruta_audio1 ruta_audio2 ...]
Sin rutas, abre el selector de archivos de macOS.
"""
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import anyio

from .config import cargar_config
from .deteccion import EXTENSIONES_AUDIO
from .dialogo_no_reconocido import _escapar, elegir_ramo
from .procesar_manual import procesar_grabacion_manual

TITULO = "Grabacion aparte"

# Derivado de EXTENSIONES_AUDIO en vez de escrito a mano: si algun dia el
# pipeline acepta un formato mas, el selector tiene que aceptarlo el mismo dia.
# Dos listas separadas terminarian con el selector rechazando un audio que el
# resto del sistema si sabe procesar.
TIPOS_AUDIO = sorted(e.lstrip(".") for e in EXTENSIONES_AUDIO)


def _elegir_archivos() -> list[Path]:
    """Selector nativo de macOS. Lista vacia si cancelo."""
    tipos = ", ".join(_escapar(t) for t in TIPOS_AUDIO)
    script = (
        f"choose file with prompt {_escapar('Elige la grabacion (o varias partes de la misma):')} "
        f"of type {{{tipos}}} with multiple selections allowed"
    )
    resultado = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if resultado.returncode != 0:
        return []
    # osascript devuelve los alias separados por coma, en formato HFS
    # ("Macintosh HD:Users:..."), no POSIX. Convertirlos uno por uno.
    rutas = []
    for alias in resultado.stdout.strip().split(", "):
        if not alias:
            continue
        conv = subprocess.run(
            ["osascript", "-e", f'POSIX path of (("{alias}") as alias)'],
            capture_output=True, text=True,
        )
        if conv.returncode == 0 and conv.stdout.strip():
            rutas.append(Path(conv.stdout.strip()))
    return rutas


def _pedir_fecha(fecha_detectada: date) -> date | None:
    """
    La fecha detectada viene del mtime del archivo, que no es confiable: pasar
    por AirDrop o copiar el archivo lo reescribe con la fecha de la copia. En
    el flujo de clases eso ya fusiono dos clases de ramos distintos, y por eso
    ahi manda la fecha del nombre del archivo.

    Aca no hay nombre de archivo con fecha del que fiarse, asi que se pregunta
    y se muestra la detectada como valor por defecto. Importa mas que en una
    clase: si la grabacion es una reunion donde se reparten responsabilidades,
    la fecha es parte de lo que respalda quien dijo que cosa y cuando.

    None significa que cancelo.
    """
    prompt = (
        f"Fecha de la grabacion.\n\n"
        f"Detecte {fecha_detectada.isoformat()} a partir del archivo, pero esa fecha "
        f"cambia sola al copiar o pasar por AirDrop. Corrigela si no es la correcta."
    )
    script = (
        f"display dialog {_escapar(prompt)} "
        f"default answer {_escapar(fecha_detectada.isoformat())} "
        f"with title {_escapar(TITULO)}"
    )
    while True:
        resultado = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if resultado.returncode != 0:
            return None
        m = re.search(r"text returned:(.*)$", resultado.stdout.strip())
        if not m:
            return None
        try:
            return date.fromisoformat(m.group(1).strip())
        except ValueError:
            # Reintenta en vez de abortar: escribir mal una fecha es un desliz
            # de tipeo, no una razon para perder todo lo elegido hasta aqui.
            _avisar("Esa fecha no se entiende. Escribela como 2026-08-26 (ano-mes-dia).")


def _confirmar(archivos: list[Path], ramo: str, fecha: date) -> bool:
    """
    Ultima pantalla antes de trabajar. Dice explicitamente que el audio se
    mueve, porque es lo unico de todo el flujo que cambia algo fuera del
    proyecto y no tiene vuelta atras comoda: procesar_grabacion_manual MUEVE
    los originales a Procesados/[Ramo]/ al terminar, no los copia.
    """
    lista = "\n".join(f"  - {a.name}" for a in archivos)
    mensaje = (
        f"Voy a procesar esta grabacion como:\n\n"
        f"Ramo: {ramo}\n"
        f"Fecha: {fecha.isoformat()}\n\n"
        f"Archivo(s):\n{lista}\n\n"
        f"Al terminar vas a tener las notas en Obsidian y el documento en Output. "
        f"El audio original se mueve a Procesados/{ramo}/ (no se copia: deja de estar "
        f"donde esta ahora).\n\n"
        f"Toma entre 10 y 25 minutos. Te aviso cuando termine."
    )
    script = (
        f"display dialog {_escapar(mensaje)} "
        f"buttons {{{_escapar('Cancelar')}, {_escapar('Procesar')}}} "
        f"default button {_escapar('Procesar')} "
        f"with title {_escapar(TITULO)}"
    )
    resultado = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if resultado.returncode != 0:
        return False
    return "button returned:Procesar" in resultado.stdout


def _avisar(mensaje: str) -> None:
    script = (
        f"display dialog {_escapar(mensaje)} buttons {{{_escapar('Entendido')}}} "
        f"default button {_escapar('Entendido')} with title {_escapar(TITULO)}"
    )
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True)


def preparar(rutas: list[str]) -> dict | None:
    """
    Todo el dialogo con el estudiante, sin tocar ningun archivo. Devuelve lo
    que hace falta para llamar a procesar_grabacion_manual, o None si cancelo
    en cualquier paso.

    Separado del procesamiento para poder probar las decisiones sin mover
    audios ni gastar llamadas al modelo.
    """
    archivos = [Path(r).expanduser().resolve() for r in rutas] if rutas else _elegir_archivos()
    if not archivos:
        return None

    faltantes = [a for a in archivos if not a.is_file()]
    if faltantes:
        _avisar("No encontre este archivo:\n" + "\n".join(str(f) for f in faltantes))
        return None

    config = cargar_config()

    seleccion = elegir_ramo(config)
    if seleccion is None:
        # Cerrar la ventana del ramo cancela y no pasa nada. A diferencia del
        # flujo de Input, aca no hay nada que rescatar a medias: los audios
        # siguen intactos donde estaban y se puede volver a empezar.
        return None
    ramo, perfil_whisper, _contexto = seleccion

    en_orden = sorted(archivos, key=lambda p: p.stat().st_mtime)
    fecha = _pedir_fecha(date.fromtimestamp(en_orden[0].stat().st_mtime))
    if fecha is None:
        return None

    if not _confirmar(en_orden, ramo, fecha):
        return None

    return {
        "rutas": [str(p) for p in en_orden],
        "ramo": ramo,
        "perfil_whisper": perfil_whisper,
        "fecha": fecha.isoformat(),
    }


def main(rutas: list[str]) -> int:
    plan = preparar(rutas)
    if plan is None:
        print("Cancelado. No se toco ningun archivo.")
        return 0

    try:
        ruta_docx = anyio.run(
            procesar_grabacion_manual,
            plan["rutas"], plan["ramo"], plan["perfil_whisper"], plan["fecha"],
        )
    except Exception as e:
        # La app de doble clic no tiene terminal a la vista, asi que un error
        # sin dialogo seria un silencio total.
        _avisar(f"No pude terminar de procesar la grabacion.\n\n{type(e).__name__}: {e}")
        raise

    print(f"Listo: {ruta_docx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

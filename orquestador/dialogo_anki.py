"""
Aviso al empezar cuando Anki no esta abierto.

Por que existe. Las flashcards se agregan al final del procesamiento, o sea
diez o veinte minutos despues del clic. Si Anki estaba cerrado, hasta ahora el
estudiante se enteraba ahi, cuando ya no estaba mirando, y quedaba con las
preguntas escritas en la nota pero sin tarjetas: para arreglarlo tenia que
agregarlas a mano una por una. El momento util para avisar es antes de
empezar, que es justo cuando esta frente al Mac porque acaba de hacer clic.

Que NO hace: bloquear. Si nadie contesta, el procesamiento sigue sin Anki, que
es exactamente lo que pasaba antes y no rompe nada. Un aviso sobre flashcards
no puede terminar impidiendo que la clase se procese.
"""
import re
import subprocess
import time

from . import anki_connect

TIMEOUT_SEGUNDOS = 120

# Cuantas veces se puede decir "ya lo abri" antes de seguir igual. Sin tope, un
# Anki que no levanta dejaria el dialogo dando vueltas para siempre.
INTENTOS_MAXIMOS = 3

OPCION_YA_ABRI = "Ya lo abrí, continuar"
OPCION_SEGUIR = "Continuar sin Anki"


def _escapar(texto: str) -> str:
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _preguntar(reintento: bool) -> str:
    mensaje = (
        "Anki está cerrado, así que esta clase quedaría sin flashcards.\n\n"
        "Ábrelo y dale a continuar. Las preguntas igual quedan guardadas en la "
        "nota de aprendizaje, pero tendrías que pasarlas a Anki a mano."
    )
    if reintento:
        mensaje = (
            "Todavía no detecto Anki.\n\n"
            "Revisa que esté completamente abierto (y que tenga el complemento "
            "AnkiConnect instalado). Cuando esté listo, dale a continuar."
        )
    botones = ", ".join(_escapar(o) for o in (OPCION_SEGUIR, OPCION_YA_ABRI))
    script = (
        f"display dialog {_escapar(mensaje)} "
        f"buttons {{{botones}}} "
        f"default button {_escapar(OPCION_YA_ABRI)} "
        f'with title "Anki está cerrado" '
        f"giving up after {TIMEOUT_SEGUNDOS}"
    )
    resultado = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if resultado.returncode != 0:
        return OPCION_SEGUIR  # cerro la ventana: seguir es lo que no rompe nada
    m = re.search(r"button returned:([^,]*), gave up:(true|false)", resultado.stdout.strip())
    if not m or m.group(2) == "true" or not m.group(1):
        return OPCION_SEGUIR  # se vencio el tiempo: no esta mirando, seguir igual
    return m.group(1)


def confirmar_antes_de_empezar() -> bool:
    """
    Devuelve True siempre que haya que seguir con el procesamiento.

    Si Anki ya esta abierto no muestra nada: el aviso solo aparece cuando de
    verdad hay algo que avisar. Y si el estudiante dice que ya lo abrio, se
    vuelve a comprobar de verdad en vez de creerle: Anki puede estar abriendose
    todavia, o faltarle el complemento.
    """
    for intento in range(INTENTOS_MAXIMOS):
        if anki_connect.verificar_conexion():
            return True
        if _preguntar(reintento=intento > 0) == OPCION_SEGUIR:
            return True
        # Dijo que ya lo abrio: darle un momento a AnkiConnect para responder.
        time.sleep(2)
    return True

"""
Pantalla que muestra todas las grabaciones de Input antes de empezar, con lo
que el sistema detecto de cada una, y deja corregir lo que este mal.

Por que todas juntas y por que al principio:

El dialogo anterior (dialogo_no_reconocido.py) pregunta por una grabacion a la
vez, dentro del bucle que las procesa. Con dos grabaciones dudosas eso son dos
interrupciones separadas por 20 minutos de transcripcion, y la segunda llega
cuando el estudiante ya se fue. El flujo entero de la app es "suelto la clase
y me voy": toda pregunta tiene que caber en los primeros segundos, mientras
todavia esta frente al Mac por el clic que acaba de dar.

Que pasa si nadie contesta. La ventana tiene el mismo timeout de 10 minutos
que el dialogo viejo, y vencerlo NO descarta nada:

  - Las grabaciones que el sistema reconocio se procesan igual, que es
    exactamente lo que pasaba antes de que esta pantalla existiera.
  - Las dudosas quedan sin tocar, en Input, para el proximo clic. No se
    ignoran, no se archivan a medias, no se adivina su ramo.

Asi el caso "dejo la clase y me voy" sigue funcionando sin cambios, y lo unico
que exige presencia es lo que de verdad no se puede decidir solo.

Por que Swift. Una lista con un menu por fila necesita AppKit, y desde Python
eso obliga a PyObjC o rumps: dependencias grandes para una ventana. swiftc ya
viene con las herramientas de linea de comandos de Xcode y produce un binario
chico sin nada que instalar. Mismo criterio que barra_menu/BarraEstado.swift.

Si el binario no esta compilado (swiftc ausente, o nunca se corrio
compilar_apps.sh), esto NO es un error: se cae al dialogo de siempre, uno por
grabacion. La pantalla es una mejora de comodidad, no un requisito para
procesar una clase.

Contrato con el binario, por stdin/stdout en JSON. Se eligio eso y no un
archivo temporal para que no quede basura si la ventana muere de forma abrupta,
y para que no haya dos procesos escribiendo el mismo archivo.
"""
import json
import subprocess
from pathlib import Path

from . import ramo_por_nombre
from .estado_vivo import duracion_audio_segundos

BINARIO = Path(__file__).parent.parent / "ventana_confirmacion" / "ConfirmarGrabaciones"

TIMEOUT_SEGUNDOS = 600

# Que hacer con cada grabacion. Son los mismos caminos que ofrecia el dialogo
# viejo, con los mismos nombres, para que el resto del pipeline no tenga que
# distinguir por donde se decidio.
PROCESAR = "procesar"
SOLO_TRANSCRIBIR = "solo_transcribir"
OMITIR = "omitir"


def _duracion_minutos(archivos: list[str]) -> int | None:
    """Suma de las partes. None si ffprobe no puede con alguna: es preferible
    no mostrar duracion a mostrar una incompleta, que en una grabacion cortada
    en partes se veria como si faltara la mitad de la clase."""
    total = 0.0
    for ruta in archivos:
        segundos = duracion_audio_segundos(ruta)
        if segundos is None:
            return None
        total += segundos
    return round(total / 60)


def describir(trabajos: list[dict], config: dict) -> dict:
    """
    Lo que la ventana necesita saber. Se arma aca y no en Swift porque el
    binario tiene que poder ser tonto: recibe, muestra, devuelve. Toda la
    logica de que ramo salio de donde vive en Python, donde hay pruebas.
    """
    grabaciones = []
    for t in trabajos:
        estado, _ = ramo_por_nombre.resolver(
            [Path(a).name for a in t["archivos"]], config
        )
        grabaciones.append({
            "clave": t["clave"],
            "archivos": [Path(a).name for a in t["archivos"]],
            "fecha": t["fecha"],
            "dia_semana": t["dia_semana"],
            "duracion_min": _duracion_minutos(t["archivos"]),
            "ramo": t.get("ramo"),
            "reconocido": bool(t.get("reconocido")),
            # De donde salio el ramo, para que la ventana pueda decirlo en vez
            # de mostrar un dato sin explicar de donde viene.
            "origen": ("nombre" if estado == ramo_por_nombre.RECONOCIDO
                       else "dia" if t.get("reconocido") else None),
        })
    return {
        "grabaciones": grabaciones,
        "ramos": sorted(ramo_por_nombre.ramos_conocidos(config)),
        "timeout_segundos": TIMEOUT_SEGUNDOS,
    }


def _decisiones_por_defecto(descripcion: dict) -> dict[str, dict]:
    """
    Lo que pasa sin intervencion: se procesa lo reconocido y no se toca el
    resto. Es el comportamiento anterior a esta pantalla, y es a lo que se cae
    cuando la ventana no esta, no abre, o vence el tiempo.
    """
    decisiones = {}
    for g in descripcion["grabaciones"]:
        if g["reconocido"]:
            decisiones[g["clave"]] = {"que_hacer": PROCESAR, "ramo": g["ramo"]}
        else:
            decisiones[g["clave"]] = {"que_hacer": OMITIR}
    return decisiones


def _validar(respuesta: dict, descripcion: dict) -> dict[str, dict] | None:
    """
    La respuesta de la ventana no se cree sin revisar. Un binario que devuelve
    una clave que no existe, o un ramo vacio, tiene que caer al comportamiento
    por defecto en vez de romper el procesamiento a mitad de camino.
    """
    if respuesta.get("accion") != PROCESAR:
        return None
    claves_validas = {g["clave"] for g in descripcion["grabaciones"]}
    decisiones = {}
    for d in respuesta.get("decisiones", []):
        clave = d.get("clave")
        que_hacer = d.get("que_hacer")
        if clave not in claves_validas or que_hacer not in (PROCESAR, SOLO_TRANSCRIBIR, OMITIR):
            return None
        if que_hacer == PROCESAR and not (d.get("ramo") or "").strip():
            return None
        decisiones[clave] = {
            "que_hacer": que_hacer,
            "ramo": (d.get("ramo") or "").strip() or None,
            "ramo_nuevo": bool(d.get("ramo_nuevo")),
        }
    # Una grabacion sobre la que la ventana no dijo nada conserva su default.
    for clave, defecto in _decisiones_por_defecto(descripcion).items():
        decisiones.setdefault(clave, defecto)
    return decisiones


def preguntar(trabajos: list[dict], config: dict) -> dict[str, dict] | None:
    """
    Devuelve que hacer con cada trabajo, indexado por su clave.

    None significa "esta pantalla no esta disponible, sigue por el camino de
    siempre" (el dialogo de a una grabacion por vez). Se devuelve solo cuando
    el binario no esta compilado, y es distinto de un diccionario de decisiones
    por defecto: sin binario, una grabacion no reconocida TIENE que seguir
    preguntando por el camino viejo, o se dejaria de preguntar algo que hoy si
    se pregunta.

    Nunca levanta una excepcion. Si la ventana existe pero falla (no arranca,
    devuelve basura, se queda colgada, vence el tiempo) se cae al
    comportamiento por defecto, que es el que habia antes de esta pantalla:
    procesar lo reconocido y dejar el resto para el proximo clic.
    """
    descripcion = describir(trabajos, config)
    if not descripcion["grabaciones"]:
        return {}
    if not BINARIO.is_file():
        return None

    try:
        proceso = subprocess.run(
            [str(BINARIO)],
            input=json.dumps(descripcion, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEGUNDOS + 30,
        )
        respuesta = json.loads(proceso.stdout.strip() or "{}")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return _decisiones_por_defecto(descripcion)

    validadas = _validar(respuesta, descripcion)
    return validadas if validadas is not None else _decisiones_por_defecto(descripcion)

"""
Resuelve el ramo de una grabacion leyendo el nombre del archivo, antes de
mirar el calendario.

Por que el nombre y no el dia de la semana:

El sistema resolvia el ramo con una sola regla, dia -> ramo. Eso significa que
un miercoles SIEMPRE era la clase del miercoles, sin manera de decir otra cosa.
El 26-08-2026 una reunion informativa de un ramo anexo, grabada ese miercoles,
quedo archivada como clase de BIOLOGIA CELULAR, y ademas choco de
numero con la clase real de ese dia (las dos quedaron "Clase 04"). Nadie
pregunto nada porque el dia si tenia ramo asignado.

El dato para evitarlo ya estaba: el archivo se llamaba
"Evaluacion conocimientos intermedios 26.08.26.m4a". El estudiante escribe el ramo
en el nombre de cada grabacion, y el sistema solo leia la fecha de ahi.

Esta es la misma regla que ya rige para la fecha ("la fecha del nombre manda
sobre el mtime del archivo", ver _resolver_fecha_archivo en deteccion.py),
extendida al ramo. El mtime no era confiable porque cambia al copiar o pasar
por AirDrop; el dia de la semana no es confiable porque no todo lo que se
graba un miercoles es la clase del miercoles.

Tres resultados posibles, y la diferencia entre los dos ultimos importa:

  - RECONOCIDO: el nombre calza con un ramo conocido. Manda sobre el dia.
  - SIN_SENAL: el nombre no dice nada util ("Nota de voz 3.m4a"). Se cae al
    dia de la semana, que es el comportamiento de siempre.
  - NO_CALZA: el nombre tiene palabras reales que no son ningun ramo conocido
    ("Reunion de coordinacion"). Eso es una senal positiva de que NO es
    una clase, asi que dispara el dialogo en vez de adivinar por el dia.

Colapsar SIN_SENAL y NO_CALZA en "no se sabe" seria mas simple y estaria mal:
un archivo sin nombre util no es evidencia de nada, y uno que dice
"Reunion de coordinacion" si lo es.

Calibracion, medida contra los 27 nombres reales que ya pasaron por el sistema:

  - Las 22 clases del semestre dan 1.00 con su ramo. Ninguna pediria confirmar.
  - "Analicis Numerico III" (con la falta de ortografia del estudiante) calza
    con TALLER DE ANÁLISIS NUMÉRICO III.
  - "Sistema y estructura digital" (en singular) calza con MERCADOS Y
    ESTRUCTURA ECONOMICA.
  - "Evaluacion conocimientos intermedios" da 0.00 contra los cinco ramos del
    horario, o sea que el caso que motivo todo esto habria preguntado.

El umbral quedo en 0.60 y la distancia entre el peor acierto (1.00) y el mejor
falso positivo (0.00) es todo el rango, asi que hay margen de sobra. Si algun
dia un nombre nuevo cae mal clasificado, muevelo con datos, no a ojo: el
diccionario de pruebas de tests/test_orquestador.py tiene los casos reales.
"""
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

UMBRAL_COINCIDENCIA = 0.60

# Cuanto se parecen dos palabras sueltas para contarlas como la misma. A 0.85,
# "analitics"/"analytics" y "mercado"/"mercados" pasan, y palabras distintas de
# largo parecido no.
UMBRAL_PALABRA = 0.85

RECONOCIDO = "reconocido"
SIN_SENAL = "sin_senal"
NO_CALZA = "no_calza"

# Palabras que no distinguen un ramo de otro. Sin esto, "Clase de termodinamica"
# y "Clase de marketing" comparten "clase" y se acercan artificialmente.
PALABRAS_IGNORADAS = {
    "de", "del", "la", "el", "los", "las", "y", "e", "en", "con", "a", "al",
    "i", "ii", "iii", "iv", "v",
}

# Palabras que aparecen en un nombre sin decir nada del ramo. Un archivo que
# solo tiene estas no es evidencia de nada: se cae al dia de la semana.
PALABRAS_SIN_CONTENIDO = {
    "grabacion", "grabaciones", "audio", "nota", "notas", "voz", "clase",
    "clases", "nueva", "nuevo", "parte", "partes", "rec", "recording",
    "memo", "sin", "titulo", "documento", "archivo", "untitled", "new",
}


def normalizar(texto: str) -> str:
    """Minusculas, sin tildes ni signos. La n con virgulilla se conserva como n,
    que es justo lo que hace falta para que "Biologia" calce con "BIOLOGIA"."""
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    sin_tildes = "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", sin_tildes)


def limpiar_nombre_archivo(nombre: str) -> str:
    """
    Deja solo la parte del nombre que puede hablar del ramo: saca la extension,
    el sufijo de parte que agrega el propio sistema al cortar un audio largo, y
    las fechas en cualquiera de los formatos que el estudiante usa (24.08.26,
    3-8-26, 18.8.26).
    """
    sin_ext = re.sub(r"\.[a-z0-9]{2,4}$", "", nombre, flags=re.IGNORECASE)
    sin_parte = re.sub(r"[-\s]*parte\s*\d+", " ", sin_ext, flags=re.IGNORECASE)
    sin_fecha = re.sub(r"\d{1,4}[.\-/]\d{1,2}([.\-/]\d{2,4})?", " ", sin_parte)
    return normalizar(sin_fecha).strip()


def _palabras_utiles(texto: str) -> set[str]:
    """
    Los numeros sueltos se descartan siempre. En un nombre de archivo son
    correlativos o restos de fecha ("Nota de voz 3", "Termodinamica 3"), nunca el
    ramo: los ramos que llevan numero lo escriben en romano ("III"), que si
    sobrevive. Dejarlos pasar rompia por los dos lados: "Nota de voz 3" parecia
    tener contenido real por culpa del 3, y "Termodinamica 3" bajaba a 0.50
    porque el numero contaba como palabra que no calza.
    """
    return {
        p for p in normalizar(texto).split()
        if p and p not in PALABRAS_IGNORADAS and not p.isdigit()
    }


def _puntaje(nombre_limpio: str, ramo: str) -> float:
    """
    Fraccion de las palabras del nombre que aparecen en el ramo. Se mide sobre
    el nombre y no sobre el ramo a proposito: "Termodinamica 13.08.26" tiene que
    dar 1.00 contra "TERMODINAMICA" aunque el ramo tuviera mas palabras, y
    "Analicis Numerico III" tiene que dar 1.00 contra "TALLER EN BUSINESS
    ANALYTICS III" sin que la palabra "taller", que el estudiante nunca
    escribe, lo penalice.
    """
    del_nombre = _palabras_utiles(nombre_limpio)
    del_ramo = _palabras_utiles(ramo)
    if not del_nombre or not del_ramo:
        return 0.0
    aciertos = sum(
        1 for palabra in del_nombre
        if any(SequenceMatcher(None, palabra, otra).ratio() >= UMBRAL_PALABRA
               for otra in del_ramo)
    )
    return aciertos / len(del_nombre)


def ramos_conocidos(config: dict) -> dict[str, str]:
    """Nombre de ramo -> perfil de whisper, juntando el horario y los adicionales."""
    del_horario = {
        r["nombre"]: r.get("perfil_whisper", "es-chile")
        for r in config.get("ramos", {}).values()
    }
    adicionales = {
        nombre: info.get("perfil_whisper", "es-chile")
        for nombre, info in config.get("ramos_adicionales", {}).items()
    }
    return {**del_horario, **adicionales}


def resolver(nombres_archivo: list[str], config: dict) -> tuple[str, dict | None]:
    """
    Devuelve (estado, ramo_info). ramo_info trae nombre y perfil_whisper, con
    la misma forma que devuelve resolver_ramo en deteccion.py, para que quien
    llama no tenga que distinguir de donde salio.

    Si el trabajo trae varias partes de una misma grabacion, todas tienen que
    apuntar al mismo ramo. Que no coincidan significa que se agruparon archivos
    de clases distintas, y eso ya fusiono dos ramos en un solo documento antes
    (la del primer dia con Termodinamica del 20). Ante esa duda se pregunta.
    """
    conocidos = ramos_conocidos(config)
    if not conocidos or not nombres_archivo:
        return SIN_SENAL, None

    resultados = []
    for nombre in nombres_archivo:
        limpio = limpiar_nombre_archivo(Path(nombre).name)
        con_contenido = {
            p for p in _palabras_utiles(limpio) if p not in PALABRAS_SIN_CONTENIDO
        }
        if not con_contenido:
            resultados.append((SIN_SENAL, None))
            continue
        puntaje, ramo = max((_puntaje(limpio, r), r) for r in conocidos)
        if puntaje >= UMBRAL_COINCIDENCIA:
            resultados.append((RECONOCIDO, ramo))
        else:
            resultados.append((NO_CALZA, None))

    reconocidos = {ramo for estado, ramo in resultados if estado == RECONOCIDO}
    if len(reconocidos) > 1:
        return NO_CALZA, None
    if reconocidos:
        ramo = reconocidos.pop()
        return RECONOCIDO, {"nombre": ramo, "perfil_whisper": conocidos[ramo]}
    # Ninguna parte reconocio un ramo. Basta que una traiga palabras reales que
    # no calzan para que valga la pena preguntar.
    if any(estado == NO_CALZA for estado, _ in resultados):
        return NO_CALZA, None
    return SIN_SENAL, None

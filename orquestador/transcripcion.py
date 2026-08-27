"""
Transcripcion orquestada de los trabajos que arma la etapa 2 (deteccion).

Procesa los trabajos pendientes de a uno a la vez, sin paralelismo (Whisper
es intensivo en CPU/GPU del M3, no queremos varias transcripciones compitiendo
por los mismos nucleos). Si un trabajo tiene varias partes de audio (una clase
grabada en mas de un archivo), se transcriben en el orden cronologico ya
resuelto por la etapa 2 y se concatena el texto.

Antes de transcribir nada se pregunta por todas las grabaciones juntas, en
una sola pantalla (pantalla_confirmacion.py). Eso existe porque el estudiante
esta frente al Mac solo en los primeros segundos, por el clic que acaba de
dar: preguntar dentro del bucle significaba interrumpirlo 20 minutos despues,
cuando ya se habia ido.

Si esa pantalla no esta compilada, se sigue por el camino anterior: un dialogo
nativo por grabacion no reconocida (dialogo_no_reconocido.py), con las mismas
tres salidas de siempre (solo transcribir, elegir el ramo a mano, o ignorar).

Con el ramo resuelto, el texto queda listo para que la etapa 4 (skill
transcripciones-a-conocimiento) lo procese.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

from . import estado_vivo, pantalla_confirmacion, ramo_por_nombre
from .config import cargar_config, dir_pendientes, guardar_config
from .deteccion import construir_trabajos, marcar_emitido
from .dialogo_no_reconocido import preguntar_que_hacer
from .nombres import calcular_numero_clase_por_orden, slug_pendiente
from .notificaciones import notificar_error, notificar_progreso
from .uso import registrar_transcripcion

PERFIL_WHISPER_POR_DEFECTO = "es-chile"


def _obtener_transcribe(transcriptotem_dir: str):
    ruta = str(Path(transcriptotem_dir))
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
    from backend.transcriber import transcribe
    return transcribe


def transcribir_trabajo(trabajo: dict, config: dict) -> str:
    transcribe = _obtener_transcribe(config["rutas"]["transcriptotem"])
    perfil = trabajo["perfil_whisper"] or PERFIL_WHISPER_POR_DEFECTO
    contexto = trabajo.get("contexto") or ""
    archivos = trabajo["archivos"]
    partes = []
    for i, ruta_audio in enumerate(archivos, start=1):
        detalle = f"Parte {i} de {len(archivos)}" if len(archivos) > 1 else trabajo["fecha"]
        # La transcripcion es la unica etapa cuyo tiempo si se puede estimar
        # de antemano: depende de la duracion del audio, no del modelo.
        duracion = estado_vivo.duracion_audio_segundos(ruta_audio)
        eta = duracion / estado_vivo.velocidad_transcripcion() if duracion else None
        notificar_progreso(estado_vivo.PASO_TRANSCRIBIR, detalle, eta,
                           sub=(i, len(archivos)) if len(archivos) > 1 else None)
        comenzo = time.monotonic()
        # Los audios largos se cortan solos antes de transcribir: uno de casi
        # dos horas devolvia cero texto sin dar error (ver _transcribir_archivo).
        # La verificacion de que salio texto ocurre tramo por tramo ahi adentro.
        texto = _transcribir_archivo(transcribe, ruta_audio, perfil, contexto, duracion, detalle)
        # Con la medicion real, la estimacion de la proxima clase deja de
        # depender de una constante escrita a mano (ver uso.py).
        registrar_transcripcion(trabajo.get("clave", "?"), duracion, time.monotonic() - comenzo)
        if len(archivos) > 1:
            texto = f"--- Parte {i} ({Path(ruta_audio).name}) ---\n{texto}"
        partes.append(texto)

    return "\n\n".join(partes)


# Una clase deja del orden de 900 caracteres por minuto de audio (medido sobre
# grabaciones reales). El umbral se pone muy por debajo: no busca juzgar si la
# transcripcion es buena, solo distinguir "hay clase aca" de "no salio nada".
CARACTERES_MINIMOS_POR_MINUTO = 100
MINIMO_ABSOLUTO = 200

# Duracion a partir de la cual el audio se corta antes de transcribirlo, y
# tamano de cada trozo.
#
# Existe por una clase real de 1 h 56 min: Whisper corrio 14 minutos y devolvio
# CERO caracteres, sin lanzar ningun error. Comprobado en vivo que el mismo
# audio si se transcribe bien por tramos (60 s dan 752 caracteres, 15 min dan
# 13.452), o sea que el problema es el largo del archivo, no la grabacion.
#
# No se sabe donde esta exactamente el limite y averiguarlo cuesta una corrida
# de varios minutos por prueba, asi que se corta muy por debajo: 20 minutos
# esta probado y 35 deja pasar directo a las clases cortas. Cortar de mas no
# cuesta casi nada (la copia es sin recodificar, segundos) y ademas da un
# avance visible mas fino en el icono de la barra.
PREFIJO_TROZOS = "trozos_"
UMBRAL_PARTIR_SEGUNDOS = 35 * 60
DURACION_TROZO_SEGUNDOS = 20 * 60


def _borrar_carpeta_de_trozos(carpeta: Path) -> None:
    """
    Borra la carpeta temporal de trozos, y solo esa.

    Este es el unico borrado que hace el sistema por su cuenta, asi que se
    escribe para que NO PUEDA alcanzar otra cosa, en vez de para que "no
    deberia":

    1. La carpeta la crea `tempfile.mkdtemp()` en el area temporal del sistema,
       con un nombre unico e irrepetible. No es una carpeta del estudiante:
       Input, Procesados y el vault estan fuera de su alcance por construccion.
    2. No se borra por patron ni por nombre. No hay glob, ni comodines, ni
       nombres armados con datos del audio. Se borra exactamente la ruta que
       este mismo modulo acaba de crear y tiene en una variable. Un patron es
       la forma en que estos borrados se vuelven catastroficos.
    3. Antes de borrar se comprueba que la ruta siga estando dentro del area
       temporal del sistema y conserve el prefijo con el que se creo. Si algo
       no calza, no se borra nada y se sigue: una carpeta temporal de sobra no
       le hace dano a nadie.
    4. El audio original nunca esta aca adentro. Los trozos son copias; el
       original se lee y se archiva despues, intacto.
    """
    try:
        resuelta = carpeta.resolve()
        raiz_temporal = Path(tempfile.gettempdir()).resolve()
        dentro_del_area_temporal = (
            resuelta != raiz_temporal and resuelta.is_relative_to(raiz_temporal)
        )
        if not (dentro_del_area_temporal and resuelta.name.startswith(PREFIJO_TROZOS)):
            return
        shutil.rmtree(resuelta, ignore_errors=True)
    except Exception:
        pass  # no borrar nunca puede costar mas que no limpiar


def _partir_audio(ruta_audio: str, carpeta: Path) -> list[Path]:
    """
    Corta un audio largo en trozos, sin recodificar.

    Los trozos son temporales y se borran al terminar: el archivo original no
    se toca, y se archiva despues como cualquier otro. El corte cae en un punto
    cualquiera de la clase, asi que en cada empalme se puede perder una palabra
    a medias. Con cinco o seis empalmes en una clase de dos horas eso es mucho
    menos dano que perder la clase entera, que es lo que pasaba antes.
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    patron = carpeta / f"{Path(ruta_audio).stem} - trozo %03d{Path(ruta_audio).suffix}"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(ruta_audio), "-f", "segment",
         "-segment_time", str(DURACION_TROZO_SEGUNDOS), "-c", "copy", str(patron), "-y"],
        check=True, capture_output=True,
    )
    return sorted(carpeta.glob(f"{Path(ruta_audio).stem} - trozo *"))


def _transcribir_archivo(transcribe, ruta_audio: str, perfil: str, contexto: str,
                         duracion: float | None, etiqueta: str) -> str:
    """Transcribe un archivo, cortandolo antes si es largo."""
    if not duracion or duracion <= UMBRAL_PARTIR_SEGUNDOS:
        texto, _, _ = transcribe(ruta_audio, language_profile=perfil, context_text=contexto)
        _verificar_parte(texto, ruta_audio, duracion)
        return texto

    temporal = Path(tempfile.mkdtemp(prefix=PREFIJO_TROZOS))
    try:
        trozos = _partir_audio(ruta_audio, temporal)
        piezas = []
        for i, trozo in enumerate(trozos, start=1):
            notificar_progreso(
                estado_vivo.PASO_TRANSCRIBIR,
                f"{etiqueta}, tramo {i} de {len(trozos)}",
                (duracion / estado_vivo.velocidad_transcripcion()) * (1 - (i - 1) / len(trozos)),
                sub=(i, len(trozos)),
            )
            texto, _, _ = transcribe(str(trozo), language_profile=perfil, context_text=contexto)
            _verificar_parte(texto, trozo, estado_vivo.duracion_audio_segundos(trozo))
            piezas.append(texto.strip())
        return "\n".join(piezas)
    finally:
        _borrar_carpeta_de_trozos(temporal)


def _verificar_parte(texto: str, ruta_audio: str, duracion_s: float | None) -> None:
    """
    Corta si un audio no produjo practicamente texto.

    Existe por una clase real de casi dos horas: Whisper corrio 14 minutos y
    devolvio cero caracteres. El pipeline siguio igual, le entrego un archivo
    vacio a la skill, y lo que vio el estudiante fue "la skill no reporto
    RESULTADO_ORQUESTADOR": un mensaje que no dice nada del problema real, y
    que ademas llego despues de gastar una llamada al modelo para nada.

    Fallar aca no cuesta nada, el mensaje apunta al audio, y como el archivo
    todavia no se archivo, se puede reintentar.
    """
    utiles = len(texto.strip())
    minutos = (duracion_s or 0) / 60
    esperado = max(MINIMO_ABSOLUTO, int(minutos * CARACTERES_MINIMOS_POR_MINUTO))
    if utiles >= esperado:
        return

    nombre = Path(ruta_audio).name
    detalle = f"{utiles} caracteres para {minutos:.0f} minutos de audio" if minutos else \
              f"{utiles} caracteres"
    raise ValueError(
        f"La transcripcion de '{nombre}' salio vacia o casi vacia ({detalle}). "
        "El audio no se proceso y sigue donde estaba, se puede reintentar. "
        "Visto en vivo: las grabaciones de mas de una hora y media pueden devolver "
        "cero texto sin dar error. Si el audio es largo, cortalo en partes de unos "
        "20 a 30 minutos y dejalas todas juntas en Input: el sistema las une solas."
    )


# Una clase de una hora deja miles de caracteres. Por debajo de esto no hay
# transcripcion, hay ruido: no alcanza ni para una nota, y menos para la
# revision posterior.
MINIMO_CARACTERES_UTILES = 200


def _verificar_que_hay_texto(texto: str, archivos: list) -> None:
    """
    Corta aca si la transcripcion salio vacia o casi vacia.

    Existe por una clase real de casi dos horas: Whisper corrio 14 minutos y
    devolvio cero caracteres. El pipeline siguio igual, le paso un archivo
    vacio a la skill, y el error que vio el estudiante fue "la skill no reporto
    RESULTADO_ORQUESTADOR", que no dice nada del problema real y ademas gasto
    una llamada al modelo para nada.

    Fallar aca cuesta cero y el mensaje apunta al audio, que es donde hay que
    mirar. El audio ademas no se archiva, asi que se puede reintentar.
    """
    utiles = len(texto.strip())
    if utiles >= MINIMO_CARACTERES_UTILES:
        return
    nombres = ", ".join(Path(a).name for a in archivos)
    raise ValueError(
        f"La transcripcion quedo vacia o casi vacia ({utiles} caracteres) para: {nombres}. "
        "El audio no se proceso y sigue en su carpeta. Suele pasar cuando la grabacion "
        "esta muy baja de volumen o cuando es muy larga: probar cortandola en partes de "
        "30 a 40 minutos y dejarlas juntas en Input, que el sistema las une solas."
    )


def _guardar_pendiente(trabajo: dict, texto: str, bitacora=None) -> None:
    dir_pendientes().mkdir(parents=True, exist_ok=True)
    slug = slug_pendiente(trabajo["clave"])
    ruta_txt = dir_pendientes() / f"{slug}.txt"
    ruta_txt.write_text(texto, encoding="utf-8")
    metadata = dict(trabajo)
    metadata["archivos_originales"] = metadata.pop("archivos")
    metadata["archivo_texto"] = str(ruta_txt)
    metadata["slug"] = slug
    ruta_json = dir_pendientes() / f"{slug}.json"
    ruta_json.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if bitacora is not None:
        bitacora.archivo_creado(ruta_txt)
        bitacora.archivo_creado(ruta_json)


def _guardar_sin_clasificar(trabajo: dict, texto: str, output_dir: str) -> None:
    carpeta = Path(output_dir) / "Sin clasificar"
    carpeta.mkdir(parents=True, exist_ok=True)
    encabezado = (
        f"Fecha detectada: {trabajo['fecha']} ({trabajo['dia_semana']})\n"
        f"Archivos originales: {', '.join(Path(a).name for a in trabajo['archivos'])}\n"
        "Este audio no cayo en ningun dia de la tabla dia-ramo, asi que se \n"
        "transcribio pero no se aplicaron las skills ni se archivo nada.\n"
        "Revisar a mano.\n"
        + "-" * 60 + "\n\n"
    )
    ruta = carpeta / f"{trabajo['fecha']} - sin clasificar.txt"
    ruta.write_text(encabezado + texto, encoding="utf-8")


def _archivar_ignorado(trabajo: dict, config: dict) -> None:
    carpeta = Path(config["rutas"]["procesados"]) / "_Ignorados"
    carpeta.mkdir(parents=True, exist_ok=True)
    for origen in trabajo["archivos"]:
        origen_path = Path(origen)
        destino = carpeta / f"{trabajo['fecha']} - {origen_path.name}"
        shutil.move(str(origen_path), str(destino))


def _aplicar_decision_de_pantalla(trabajo: dict, decision: dict, config: dict) -> str:
    """
    Traduce lo que se eligio en la pantalla de confirmacion al estado que el
    resto del pipeline espera. Devuelve que hacer con el trabajo: "seguir",
    "omitir".

    Un ramo escrito a mano en la pantalla se guarda en config igual que si se
    hubiera creado por el dialogo, para que la proxima grabacion con ese nombre
    ya se reconozca sola (ver ramo_por_nombre.py).
    """
    que_hacer = decision.get("que_hacer")
    if que_hacer == pantalla_confirmacion.OMITIR:
        return "omitir"
    if que_hacer == pantalla_confirmacion.SOLO_TRANSCRIBIR:
        trabajo["reconocido"] = False
        trabajo["ramo"] = None
        return "seguir"

    ramo = decision.get("ramo")
    if decision.get("ramo_nuevo") and ramo:
        # Perfil por defecto a proposito: la pantalla no pregunta el idioma
        # para no convertir una correccion de una linea en un formulario. Se
        # ajusta despues en "Configurar Sistema" si el ramo no es en espanol.
        config.setdefault("ramos_adicionales", {}).setdefault(
            ramo, {"perfil_whisper": PERFIL_WHISPER_POR_DEFECTO, "contexto": ""}
        )
        guardar_config(config)

    ya_estaba = trabajo.get("reconocido") and trabajo.get("ramo") == ramo
    trabajo["reconocido"] = True
    trabajo["ramo"] = ramo
    trabajo["perfil_whisper"] = (
        ramo_por_nombre.ramos_conocidos(config).get(ramo) or PERFIL_WHISPER_POR_DEFECTO
    )
    if not ya_estaba:
        # Mismo motivo que en el camino del dialogo: la semana de semestre no
        # aplica a un ramo elegido a mano, y daba numeros sin sentido.
        trabajo["numero_clase"] = calcular_numero_clase_por_orden(
            Path(config["rutas"]["procesados"]), ramo, date.fromisoformat(trabajo["fecha"])
        )
        trabajo["numeracion"] = "orden"
    return "seguir"


def procesar_pendientes(config: dict | None = None, bitacora=None, decidir=None) -> list[dict]:
    """
    `decidir` existe para poder probar sin abrir ventanas. Por defecto es la
    pantalla de confirmacion, que pregunta por todas las grabaciones juntas
    antes de empezar. Si devuelve None (binario sin compilar), se sigue por el
    dialogo de a una por vez, que es el comportamiento anterior.
    """
    if config is None:
        config = cargar_config()

    trabajos = construir_trabajos(config)
    if decidir is None:
        decidir = pantalla_confirmacion.preguntar
    decisiones = decidir(trabajos, config) if trabajos else {}

    procesados = []
    for trabajo in trabajos:
        # marcar_emitido() se llama recien cuando cada camino termina bien,
        # no al principio: si la transcripcion falla a mitad de camino, el
        # audio no debe quedar en el limbo marcado como "ya hecho" para
        # siempre. Asi un reintento (otro clic) lo vuelve a tomar.
        if decisiones is not None:
            decision = decisiones.get(trabajo["clave"])
            if decision is None:
                continue  # la pantalla no dijo nada de esta: queda para el proximo clic
            if _aplicar_decision_de_pantalla(trabajo, decision, config) == "omitir":
                continue
        elif not trabajo["reconocido"]:
            decision = preguntar_que_hacer(trabajo, config)
            if decision["accion"] == "ignorar":
                _archivar_ignorado(trabajo, config)
                marcar_emitido(trabajo)
                procesados.append(trabajo)
                continue
            if decision["accion"] == "aplicar_skills":
                trabajo["reconocido"] = True
                trabajo["ramo"] = decision["ramo"]
                trabajo["perfil_whisper"] = decision["perfil_whisper"]
                trabajo["contexto"] = decision.get("contexto", "")
                # La formula de semana de semestre (calculada en deteccion.py
                # asumiendo el horario y calendario actual) no tiene sentido
                # aca: el ramo se resolvio a mano justo porque la fecha o el
                # dia no encajaban en ese calendario (visto en vivo: daba
                # numeros de clase sin sentido, ej. "Clase -2949"). Se cuenta
                # por orden cronologico entre lo ya archivado de ese ramo.
                trabajo["numero_clase"] = calcular_numero_clase_por_orden(
                    Path(config["rutas"]["procesados"]),
                    trabajo["ramo"],
                    date.fromisoformat(trabajo["fecha"]),
                )
                trabajo["numeracion"] = "orden"

        try:
            texto = transcribir_trabajo(trabajo, config)
            if trabajo["reconocido"]:
                _guardar_pendiente(trabajo, texto, bitacora)
            else:
                _guardar_sin_clasificar(trabajo, texto, config["rutas"]["output"])
        except Exception as e:
            notificar_error(
                f"{trabajo.get('ramo') or trabajo['dia_semana']} - {trabajo['fecha']}",
                f"Fallo al transcribir: {type(e).__name__}: {e}",
            )
            continue

        marcar_emitido(trabajo)
        procesados.append(trabajo)
    return procesados


if __name__ == "__main__":
    procesar_pendientes()

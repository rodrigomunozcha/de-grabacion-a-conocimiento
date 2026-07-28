"""
Transcripcion orquestada de los trabajos que arma la etapa 2 (deteccion).

Procesa los trabajos pendientes de a uno a la vez, sin paralelismo (Whisper
es intensivo en CPU/GPU del M3, no queremos varias transcripciones compitiendo
por los mismos nucleos). Si un trabajo tiene varias partes de audio (una clase
grabada en mas de un archivo), se transcriben en el orden cronologico ya
resuelto por la etapa 2 y se concatena el texto.

Si el ramo fue reconocido, el texto queda listo para que la etapa 4 (skill
transcripciones-a-conocimiento) lo procese. Si no fue reconocido (dia fuera
de la tabla dia->ramo), la etapa 8 muestra un dialogo nativo preguntando que
hacer: solo transcribir (mismo comportamiento de antes), aplicar las skills
completas igual (con un ramo elegido a mano), o ignorar el archivo.
"""
import json
import shutil
import sys
from datetime import date
from pathlib import Path

from .config import cargar_config
from .deteccion import construir_trabajos, marcar_emitido
from .dialogo_no_reconocido import preguntar_que_hacer
from .nombres import calcular_numero_clase_por_orden, slug_pendiente
from .notificaciones import notificar_error, notificar_progreso

PENDIENTES_DIR = Path(__file__).parent / "transcripciones_pendientes"
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
        notificar_progreso("Transcribiendo audio", detalle)
        texto, _, _ = transcribe(ruta_audio, language_profile=perfil, context_text=contexto)
        if len(archivos) > 1:
            texto = f"--- Parte {i} ({Path(ruta_audio).name}) ---\n{texto}"
        partes.append(texto)
    return "\n\n".join(partes)


def _guardar_pendiente(trabajo: dict, texto: str) -> None:
    PENDIENTES_DIR.mkdir(parents=True, exist_ok=True)
    slug = slug_pendiente(trabajo["clave"])
    ruta_txt = PENDIENTES_DIR / f"{slug}.txt"
    ruta_txt.write_text(texto, encoding="utf-8")
    metadata = dict(trabajo)
    metadata["archivos_originales"] = metadata.pop("archivos")
    metadata["archivo_texto"] = str(ruta_txt)
    metadata["slug"] = slug
    (PENDIENTES_DIR / f"{slug}.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )


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


def procesar_pendientes(config: dict | None = None) -> list[dict]:
    if config is None:
        config = cargar_config()

    trabajos = construir_trabajos(config)
    procesados = []
    for trabajo in trabajos:
        # marcar_emitido() se llama recien cuando cada camino termina bien,
        # no al principio: si la transcripcion falla a mitad de camino, el
        # audio no debe quedar en el limbo marcado como "ya hecho" para
        # siempre. Asi un reintento (otro clic) lo vuelve a tomar.
        if not trabajo["reconocido"]:
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
                _guardar_pendiente(trabajo, texto)
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

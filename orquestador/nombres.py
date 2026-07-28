"""
Convenciones de nombre compartidas entre la etapa 6 (docx) y el archivado de
audio. El identificador permanente de una clase es su fecha real. "Clase N"
es un numero calculado.

En el flujo automatico (dia -> ramo del horario actual), N es la semana del
semestre (calculada en deteccion.py a partir de la fecha): un valor que no
depende de que otros archivos existan, asi que nunca hay que renombrar nada
ya creado (una semana salteada simplemente deja un hueco en la numeracion).

En el flujo manual (procesar_manual.py, o el dialogo de dia no reconocido en
transcripcion.py, para grabaciones fuera del horario actual, ej. ramos de
semestres anteriores), no existe un calendario de semestre al cual anclarse,
asi que N es el orden cronologico entre las clases de ese ramo ya archivadas
en Procesados/ (ver calcular_numero_clase_por_orden). A diferencia del flujo
automatico, este numero SI depende de que otros archivos existan: si llega
una clase mas antigua que las ya archivadas, las que venian despues de ella
en la fecha deben correrse un puesto. Por eso este flujo si necesita
renombrar archivos ya creados (ver renumerar_clases_ramo), algo que se
confirmo en vivo que pasaba mal (dos clases distintas etiquetadas "Clase 01").
"""
import hashlib
import re
from datetime import date
from pathlib import Path

from docx import Document

PATRON_FECHA_EN_NOMBRE = re.compile(r"Clase \d+ - (\d{4}-\d{2}-\d{2}) - ")
PATRON_ARCHIVO_CLASE = re.compile(r"^(Clase )(\d+)( - \d{4}-\d{2}-\d{2} - .+)$")


def slug_pendiente(clave: str) -> str:
    """Identificador para los archivos intermedios en transcripciones_pendientes/
    (etapas 3 a 6). No se puede usar solo la fecha: dos clases distintas
    pueden compartir la misma fecha corrupta (visto en vivo con dos clases de
    un ramo de intercambio el mismo dia 1970), lo que hacia que la segunda se diera por "ya
    procesada" al pisar el archivo de la primera. La clave (fecha + nombres
    de archivo) si es unica por grupo de audios, asi que se usa un hash corto
    de esa clave junto a la fecha, para que el nombre siga siendo legible."""
    fecha = clave.split("|", 1)[0]
    hash_corto = hashlib.sha1(clave.encode("utf-8")).hexdigest()[:8]
    return f"{fecha}_{hash_corto}"


def sanitizar_nombre_archivo(texto: str) -> str:
    texto = re.sub(r'[/\\:*?"<>|]', "-", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def nombre_base(numero_clase: int, fecha: str, titulo: str) -> str:
    titulo_limpio = sanitizar_nombre_archivo(titulo)
    return f"Clase {numero_clase:02d} - {fecha} - {titulo_limpio}"


def calcular_numero_clase_por_orden(procesados_dir: Path, ramo: str, fecha: date) -> int:
    carpeta_ramo = procesados_dir / ramo
    fechas_existentes = set()
    if carpeta_ramo.exists():
        for archivo in carpeta_ramo.iterdir():
            m = PATRON_FECHA_EN_NOMBRE.search(archivo.name)
            if m:
                fechas_existentes.add(m.group(1))
    fechas_existentes.add(fecha.isoformat())
    return sorted(fechas_existentes).index(fecha.isoformat()) + 1


def _corregir_titulo_docx(ruta: Path, prefijo_viejo: str, prefijo_nuevo: str) -> None:
    doc = Document(str(ruta))
    for p in doc.paragraphs:
        if p.style.name == "Title" and p.text.startswith(prefijo_viejo):
            texto_nuevo = p.text.replace(prefijo_viejo, prefijo_nuevo, 1)
            for run in p.runs:
                run.text = ""
            p.runs[0].text = texto_nuevo
            break
    doc.save(str(ruta))


def renumerar_clases_ramo(procesados_dir: Path, output_dir: Path, ramo: str) -> list[tuple[Path, Path]]:
    """
    Solo para el esquema de "orden cronologico" (ver docstring del modulo):
    si el numero de clase que quedo en el nombre de un archivo ya no
    corresponde al orden real de las fechas archivadas para ese ramo (por
    ejemplo, porque llego una clase mas antigua despues), lo corrige: renombra
    el archivo (Procesados y Output) y, si es un .docx, tambien el titulo de
    la portada. Nunca toca la nota de Obsidian (esa se identifica por fecha,
    no por numero, asi que no le afecta este problema).

    No usar esto para ramos del flujo automatico (semana de semestre): ahi un
    numero salteado es real (una semana sin clase) y no se debe compactar.
    """
    carpeta_procesados = procesados_dir / ramo
    carpeta_output = output_dir / ramo

    fechas = set()
    for carpeta in (carpeta_procesados, carpeta_output):
        if not carpeta.exists():
            continue
        for archivo in carpeta.iterdir():
            m = PATRON_FECHA_EN_NOMBRE.search(archivo.name)
            if m:
                fechas.add(m.group(1))
    numero_correcto_por_fecha = {fecha: i + 1 for i, fecha in enumerate(sorted(fechas))}

    renombrados = []
    for carpeta in (carpeta_procesados, carpeta_output):
        if not carpeta.exists():
            continue
        for archivo in list(carpeta.iterdir()):
            m_completo = PATRON_ARCHIVO_CLASE.match(archivo.name)
            m_fecha = PATRON_FECHA_EN_NOMBRE.search(archivo.name)
            if not m_completo or not m_fecha:
                continue
            numero_actual = int(m_completo.group(2))
            numero_correcto = numero_correcto_por_fecha.get(m_fecha.group(1))
            if numero_correcto is None or numero_correcto == numero_actual:
                continue

            nuevo_nombre = f"{m_completo.group(1)}{numero_correcto:02d}{m_completo.group(3)}"
            nueva_ruta = carpeta / nuevo_nombre
            archivo.rename(nueva_ruta)
            if nueva_ruta.suffix == ".docx":
                _corregir_titulo_docx(
                    nueva_ruta, f"Clase {numero_actual:02d}", f"Clase {numero_correcto:02d}"
                )
            renombrados.append((archivo, nueva_ruta))
    return renombrados

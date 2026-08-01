"""
Encadena las etapas 4, 5 y 6 para las clases ya transcritas (etapa 3) y con
ramo reconocido: una sola invocacion de la skill que limpia, destila, elige
titulo y detecta los conceptos mas repetidos (etapa 4+5 fusionadas, ver
skill_runner.py), y arma el .docx y archiva el audio (etapa 6).

Los trabajos no reconocidos ya quedaron resueltos en Output/Sin clasificar
por la etapa 3 y no pasan por aqui (ver transcripcion.py).

Consume los archivos que dejo la etapa 3 en transcripciones_pendientes/:
<slug>.json (metadata del trabajo) y <slug>.txt (texto transcrito). Una vez
que una clase ya paso por aqui (existe <slug>_skill.json), no se vuelve a
procesar. El slug (ver nombres.py) no es solo la fecha: dos clases distintas
pueden compartir una fecha corrupta (visto en vivo con clases de un ramo de
intercambio), y
usar solo la fecha hacia que la segunda se diera por "ya procesada" al pisar
el archivo de la primera.
"""
import json
from pathlib import Path

from . import anki_connect
from .archivado import archivar_audio
from .carpetas import resolver_carpeta_ramo
from .config import cargar_config, guardar_config
from .docx_generator import generar_docx
from .extraer_flashcards import extraer_preguntas_respuestas
from .nombres import renumerar_clases_ramo
from .notificaciones import notificar_aviso, notificar_error, notificar_exito, notificar_progreso
from .revisor import hallazgos_graves, revisar
from .skill_runner import aplicar_skill, corregir_con_revision

PENDIENTES_DIR = Path(__file__).parent / "transcripciones_pendientes"


def _leer_nota(ruta: str | None, vault_dir: str) -> str:
    """
    Lee una de las notas que la skill dice haber escrito, para volcarla al
    .docx. Las rutas vienen del JSON que reporta el modelo, asi que se
    verifica que apunten dentro del vault antes de abrirlas: si no, una
    corrida que se desviara (ej. por texto raro colado en la transcripcion)
    podria hacer que el contenido de cualquier archivo del disco terminara
    dentro del .docx y de las flashcards de Anki. Fuera del vault se devuelve
    vacio en vez de leer: el .docx se arma igual, sin esa seccion.
    """
    if not ruta:
        return ""
    ruta_path = Path(ruta).expanduser().resolve()
    raiz_vault = Path(vault_dir).expanduser().resolve()
    if not (ruta_path == raiz_vault or ruta_path.is_relative_to(raiz_vault)):
        return ""
    if not ruta_path.is_file():
        return ""
    return ruta_path.read_text(encoding="utf-8")


def _listar_metadatas_pendientes() -> list[Path]:
    if not PENDIENTES_DIR.exists():
        return []
    return sorted(
        p for p in PENDIENTES_DIR.glob("*.json") if not p.stem.endswith("_skill")
    )


def _slug_de(trabajo_metadata: dict) -> str:
    # Con fallback a la fecha por si queda algun archivo pendiente de antes
    # de este cambio (sin campo "slug" propio).
    return trabajo_metadata.get("slug") or trabajo_metadata["fecha"]


async def _revisar_y_corregir(
    ruta_texto: str, resultado_skill: dict, ramo: str, vault_dir: str, slug: str
) -> dict:
    """
    Etapa 5: un revisor independiente compara las notas contra la transcripcion
    cruda, y si encontro algo grave, la sesion que las escribio las corrige.
    Ver revisor.py para por que la revision es una corrida aparte.

    La correccion solo se dispara con hallazgos de gravedad alta (contenido que
    la transcripcion no respalda). Los de gravedad media quedan anotados en
    <slug>_revision.json y no gastan una pasada mas: un revisor al que se le
    pide encontrar algo siempre encuentra algo, y corregir por cada detalle
    duplicaria el costo de cada clase para cambiar comas.

    Toda esta etapa es opcional por diseño. Si falla, se sigue con lo que
    escribio la skill: las notas ya estan en el vault y son utiles. Que la
    revision se caiga no puede costarle la clase al estudiante.
    """
    try:
        revision = await revisar(ruta_texto, resultado_skill, ramo, vault_dir, slug)
    except Exception as e:
        notificar_aviso(
            "La revision no corrio",
            f"{ramo}: {type(e).__name__}. Las notas quedaron como las escribio la skill, "
            "sin revisar.",
        )
        return resultado_skill

    graves = hallazgos_graves(revision)
    if revision.get("veredicto") != "corregir" or not graves:
        return resultado_skill

    notificar_progreso(
        "Corrigiendo tras la revision",
        f"{len(graves)} hallazgo(s) de gravedad alta",
    )
    try:
        return await corregir_con_revision(resultado_skill, graves, vault_dir, slug)
    except Exception as e:
        notificar_aviso(
            "La correccion no se pudo aplicar",
            f"{ramo}: {type(e).__name__}. Revisa los hallazgos en "
            f"{slug}_revision.json y corrige a mano lo que corresponda.",
        )
        return resultado_skill


async def procesar_clase_reconocida(trabajo_metadata: dict, config: dict) -> Path:
    ruta_texto = trabajo_metadata["archivo_texto"]
    ramo = trabajo_metadata["ramo"]
    slug = _slug_de(trabajo_metadata)
    vault_dir = config["rutas"]["vault_obsidian"]

    # La carpeta del ramo se resuelve aca, en Python, y se cachea en config.json:
    # buscarla es comparar nombres, no requiere criterio, y hacerlo dentro de la
    # skill obligaba a listar el vault entero en cada clase (ver carpetas.py).
    carpeta_ramo, config_cambio = resolver_carpeta_ramo(ramo, vault_dir, config)
    if config_cambio:
        guardar_config(config)

    notificar_progreso("Analizando con la skill", f"{ramo} - puede tardar unos minutos")
    resultado_skill = await aplicar_skill(
        ruta_texto, ramo, vault_dir, slug, str(carpeta_ramo)
    )

    resultado_skill = await _revisar_y_corregir(
        ruta_texto, resultado_skill, ramo, vault_dir, slug
    )

    titulo = resultado_skill["titulo"]
    conceptos = resultado_skill["conceptos_repetidos"]

    texto_fuente = _leer_nota(resultado_skill.get("fuente"), vault_dir)
    texto_aprendizaje = _leer_nota(resultado_skill.get("aprendizaje"), vault_dir)

    trabajo = dict(trabajo_metadata)
    trabajo["archivos"] = trabajo_metadata["archivos_originales"]

    notificar_progreso("Armando el .docx y archivando", titulo)
    ruta_docx = generar_docx(trabajo, titulo, texto_fuente, texto_aprendizaje, conceptos, config)
    archivar_audio(trabajo, titulo, config)

    if trabajo.get("numeracion") == "orden":
        # Solo para ramos manuales (fuera del horario con calendario propio):
        # si esta clase quedo mas antigua que otras ya archivadas, las que
        # venian despues deben correrse un puesto (ver nombres.py).
        renumerar_clases_ramo(
            Path(config["rutas"]["procesados"]), Path(config["rutas"]["output"]), ramo
        )

    tarjetas = extraer_preguntas_respuestas(texto_aprendizaje)
    if tarjetas:
        if anki_connect.verificar_conexion():
            notificar_progreso("Agregando a Anki", f"{len(tarjetas)} tarjetas")
            anki_connect.crear_mazo_si_no_existe(ramo)
            anki_connect.agregar_flashcards(ramo, tarjetas)
        else:
            notificar_aviso(
                "Faltaron las flashcards",
                f"{titulo}: Anki no estaba abierto, no se agregaron {len(tarjetas)} tarjetas. "
                "Las preguntas siguen en la nota de aprendizaje, puedes agregarlas a mano.",
            )

    notificar_exito(trabajo, titulo, ruta_docx)
    return ruta_docx


async def procesar_pendientes_reconocidos(config: dict | None = None) -> list[Path]:
    if config is None:
        config = cargar_config()

    generados = []
    for ruta_metadata in _listar_metadatas_pendientes():
        trabajo_metadata = json.loads(ruta_metadata.read_text(encoding="utf-8"))
        if not trabajo_metadata.get("reconocido"):
            continue
        ruta_skill_json = PENDIENTES_DIR / f"{_slug_de(trabajo_metadata)}_skill.json"
        if ruta_skill_json.exists():
            continue  # ya se proceso antes

        try:
            ruta_docx = await procesar_clase_reconocida(trabajo_metadata, config)
        except Exception as e:
            contexto = f"{trabajo_metadata['ramo']} - {trabajo_metadata['fecha']}"
            notificar_error(contexto, f"{type(e).__name__}: {e}")
            continue
        generados.append(ruta_docx)
    return generados


if __name__ == "__main__":
    import anyio

    anyio.run(procesar_pendientes_reconocidos)

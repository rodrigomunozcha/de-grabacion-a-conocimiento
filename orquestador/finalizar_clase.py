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

import anyio

from . import anki_connect, cancelacion
from .archivado import archivar_audio
from .carpetas import resolver_carpeta_ramo
from .config import cargar_config, dir_pendientes, guardar_config
from .docx_generator import generar_docx
from .ensayo import es_ensayo
from . import estado_vivo
from .extraer_flashcards import extraer_preguntas_respuestas
from .nombres import renumerar_clases_ramo
from .notificaciones import notificar_aviso, notificar_error, notificar_exito, notificar_progreso
from .revisor import hallazgos_graves, hallazgos_para_avisar, revisar
from .skill_runner import aplicar_skill, corregir_con_revision

# Topes de tiempo por etapa. El tope de turnos no alcanza: una llamada al SDK
# puede quedarse esperando una respuesta que no llega nunca (visto en vivo, con
# el subproceso vivo y 0% de CPU durante veinte minutos). Sin esto, una clase
# queda colgada para siempre y el estudiante no tiene forma de saberlo.
TIMEOUT_SKILL_SEGUNDOS = 45 * 60
TIMEOUT_REVISION_SEGUNDOS = 20 * 60



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
    if not dir_pendientes().exists():
        return []
    return sorted(
        p for p in dir_pendientes().glob("*.json") if not p.stem.endswith("_skill")
    )


def _slug_de(trabajo_metadata: dict) -> str:
    # Con fallback a la fecha por si queda algun archivo pendiente de antes
    # de este cambio (sin campo "slug" propio).
    return trabajo_metadata.get("slug") or trabajo_metadata["fecha"]


async def _revisar_y_corregir(
    ruta_texto: str, resultado_skill: dict, ramo: str, vault_dir: str, slug: str
) -> tuple[dict, list[dict]]:
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
    notificar_progreso(estado_vivo.PASO_REVISION, "comprobando contra la transcripcion")
    try:
        with anyio.fail_after(TIMEOUT_REVISION_SEGUNDOS):
            revision = await revisar(ruta_texto, resultado_skill, ramo, vault_dir, slug)
    except TimeoutError:
        notificar_aviso(
            "La revision tardo demasiado",
            f"{ramo}: se corto para no dejar la clase colgada. Las notas quedaron "
            "como las escribio la skill, sin revisar.",
        )
        return resultado_skill, []
    except Exception as e:
        notificar_aviso(
            "La revision no corrio",
            f"{ramo}: {type(e).__name__}. Las notas quedaron como las escribio la skill, "
            "sin revisar.",
        )
        return resultado_skill, [], []

    graves = hallazgos_graves(revision)
    if revision.get("veredicto") != "corregir" or not graves:
        return resultado_skill, hallazgos_para_avisar(revision, se_corrigio=False)

    notificar_progreso(
        estado_vivo.PASO_REVISION,
        f"corrigiendo {len(graves)} hallazgo(s) de gravedad alta",
    )
    try:
        with anyio.fail_after(TIMEOUT_REVISION_SEGUNDOS):
            corregido = await corregir_con_revision(resultado_skill, graves, vault_dir, slug)
        return corregido, hallazgos_para_avisar(revision, se_corrigio=True)
    except TimeoutError:
        notificar_aviso(
            "La correccion tardo demasiado",
            f"{ramo}: se corto. Revisa los hallazgos en {slug}_revision.json.",
        )
        return resultado_skill, hallazgos_para_avisar(revision, se_corrigio=False)
    except Exception as e:
        notificar_aviso(
            "La correccion no se pudo aplicar",
            f"{ramo}: {type(e).__name__}. Revisa los hallazgos en "
            f"{slug}_revision.json y corrige a mano lo que corresponda.",
        )
        return resultado_skill, hallazgos_para_avisar(revision, se_corrigio=False)


async def procesar_clase_reconocida(trabajo_metadata: dict, config: dict, bitacora=None) -> Path:
    ruta_texto = trabajo_metadata["archivo_texto"]
    ramo = trabajo_metadata["ramo"]
    slug = _slug_de(trabajo_metadata)
    vault_dir = config["rutas"]["vault_obsidian"]

    # La carpeta del ramo se resuelve aca, en Python, y se cachea en config.json:
    # buscarla es comparar nombres, no requiere criterio, y hacerlo dentro de la
    # skill obligaba a listar el vault entero en cada clase (ver carpetas.py).
    carpeta_ramo, config_cambio = resolver_carpeta_ramo(ramo, vault_dir, config)
    # En un ensayo el cache apunta al vault de mentira: guardarlo envenenaria
    # la configuracion real para la proxima clase de verdad.
    if config_cambio and not es_ensayo(config):
        guardar_config(config)

    # Antes de que la skill escriba nada: se respalda lo que ya habia en la
    # carpeta del ramo. Es el unico cambio que no se podria revertir despues,
    # porque la skill puede editar notas existentes (el indice del ramo) y esas
    # no se reconstruyen solas (ver bitacora.py).
    if bitacora is not None:
        bitacora.fotografiar_carpeta(carpeta_ramo)

    estado_vivo.fijar_clase(f"{ramo} - {trabajo_metadata.get('fecha', '')}")
    notificar_progreso(estado_vivo.PASO_SKILL, "puede tardar unos minutos")
    with anyio.fail_after(TIMEOUT_SKILL_SEGUNDOS):
        resultado_skill = await aplicar_skill(
            ruta_texto, ramo, vault_dir, slug, str(carpeta_ramo)
        )

    resultado_skill, hallazgos = await _revisar_y_corregir(
        ruta_texto, resultado_skill, ramo, vault_dir, slug
    )

    titulo = resultado_skill["titulo"]
    conceptos = resultado_skill["conceptos_repetidos"]

    texto_fuente = _leer_nota(resultado_skill.get("fuente"), vault_dir)
    texto_aprendizaje = _leer_nota(resultado_skill.get("aprendizaje"), vault_dir)
    # Opcional a proposito: si la skill no la genero (una clase que no
    # necesita contexto previo), el .docx se arma igual sin esa seccion.
    texto_contexto = _leer_nota(resultado_skill.get("contexto"), vault_dir)

    trabajo = dict(trabajo_metadata)
    trabajo["archivos"] = trabajo_metadata["archivos_originales"]

    notificar_progreso(estado_vivo.PASO_DOCUMENTO, titulo)
    # El unico tramo que no se puede cortar por la mitad: mover el audio lo
    # deja entre dos carpetas. Dura segundos y un aborto pedido aqui se aplica
    # apenas termina (ver cancelacion.py).
    with cancelacion.seccion_critica():
        ruta_docx = generar_docx(
            trabajo, titulo, texto_fuente, texto_aprendizaje, conceptos, config,
            texto_contexto, hallazgos,
        )
        if bitacora is not None:
            bitacora.archivo_creado(ruta_docx)
        archivar_audio(trabajo, titulo, config, bitacora)

    if trabajo.get("numeracion") == "orden":
        # Solo para ramos manuales (fuera del horario con calendario propio):
        # si esta clase quedo mas antigua que otras ya archivadas, las que
        # venian despues deben correrse un puesto (ver nombres.py).
        renumerar_clases_ramo(
            Path(config["rutas"]["procesados"]), Path(config["rutas"]["output"]), ramo
        )

    tarjetas = extraer_preguntas_respuestas(texto_aprendizaje)
    if tarjetas and es_ensayo(config):
        # Anki no tiene deshacer comodo ni mazos desechables: en un ensayo no
        # se toca, solo se informa cuantas tarjetas habrian entrado.
        notificar_progreso(estado_vivo.PASO_ANKI, f"ensayo: {len(tarjetas)} tarjetas no se agregan")
    elif tarjetas:
        if anki_connect.verificar_conexion():
            notificar_progreso(estado_vivo.PASO_ANKI, f"{len(tarjetas)} tarjetas")
            anki_connect.crear_mazo_si_no_existe(ramo)
            ids = anki_connect.agregar_flashcards(ramo, tarjetas)
            if bitacora is not None:
                bitacora.notas_anki(ids)
        else:
            notificar_aviso(
                "Faltaron las flashcards",
                f"{titulo}: Anki no estaba abierto, no se agregaron {len(tarjetas)} tarjetas. "
                "Las preguntas siguen en la nota de aprendizaje, puedes agregarlas a mano.",
            )

    notificar_exito(trabajo, titulo, ruta_docx)
    return ruta_docx


async def procesar_pendientes_reconocidos(config: dict | None = None, bitacora=None) -> list[Path]:
    if config is None:
        config = cargar_config()

    generados = []
    for ruta_metadata in _listar_metadatas_pendientes():
        trabajo_metadata = json.loads(ruta_metadata.read_text(encoding="utf-8"))
        if not trabajo_metadata.get("reconocido"):
            continue
        ruta_skill_json = dir_pendientes() / f"{_slug_de(trabajo_metadata)}_skill.json"
        if ruta_skill_json.exists():
            continue  # ya se proceso antes

        try:
            ruta_docx = await procesar_clase_reconocida(trabajo_metadata, config, bitacora)
        except Exception as e:
            contexto = f"{trabajo_metadata['ramo']} - {trabajo_metadata['fecha']}"
            notificar_error(contexto, f"{type(e).__name__}: {e}")
            continue
        generados.append(ruta_docx)
    return generados


if __name__ == "__main__":
    import anyio

    anyio.run(procesar_pendientes_reconocidos)

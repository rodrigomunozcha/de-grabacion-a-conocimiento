"""
Rehace el .docx de una clase ya procesada, con el diseño actual, sin volver a
transcribir ni volver a destilar.

Existe porque el diseño del documento va a seguir cambiando y las clases ya
procesadas no deberían quedarse con el formato del día en que se procesaron.
Todo lo caro (transcribir, entender la clase, escribir las notas) ya está
hecho y guardado: rehacer el documento es leer esas notas y volver a
dibujarlas.

Lo único que a veces falta en una clase vieja son los llamados a la acción del
profesor, porque esa sección no existía cuando se procesó. Eso sí necesita
mirar la transcripción, así que hay una llamada al modelo acotada a esa única
tarea: leer y extraer, sin escribir nada. Cuesta una fracción de reprocesar la
clase entera. Una vez extraídos quedan guardados en el `_skill.json`, así que
la siguiente regeneración de esa clase ya no cuesta nada.

Por defecto escribe en un archivo aparte y no toca el documento que ya
existe.
"""
import json
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    query,
)

from .config import cargar_config, dir_pendientes
from .docx_generator import generar_docx
from .nombres import nombre_base
from .notificaciones import notificar_aviso
from .skill_runner import (
    CLI_PATH,
    PROJECT_ROOT,
    construir_gate_de_rutas,
    describir_error_sdk,
    normalizar_resultado,
)
from .uso import registrar_uso

MARCADOR_LLAMADOS = "RESULTADO_LLAMADOS:"
MAX_TURNS = 15

SYSTEM_PROMPT = """\
Extraes de la transcripcion de una clase universitaria lo que el profesor pidio:
fechas de prueba, entregas, lecturas, cambios al programa, y sobre todo que dijo
que entra en una evaluacion. Solo lees y reportas, no escribes archivos.

La regla que manda: **cada punto lleva la frase textual del profesor**. Si no
puedes citarlo, no va. Esta lista es la que el estudiante va a usar para decidir
que estudiar, asi que una deduccion tuya aqui se convierte en una guia de estudio
falsa.

- No deduzcas. Que un tema sea importante, o que el profesor lo repita mucho, no
  significa que dijo que entra en la prueba.
- Si lo dijo a medias o el audio no permite estar seguro, marcalo con
  "seguro": false y pon en "textual" lo que alcanzo a escucharse.
- Las fechas van como el las dijo ("el jueves 12", "la ultima semana de
  septiembre"). No calcules una fecha que el no dio.
- Si en la clase no hubo ningun anuncio, devuelve las dos listas vacias. Es una
  respuesta correcta y frecuente.

Ojo con el ruido del transcriptor: la charla de antes y despues de la clase trae
coordinaciones de trabajos en grupo entre alumnos. Eso no es el profesor.

Escribe en español claro. Sin guion largo.
"""


def _construir_prompt(ruta_transcripcion: str, ramo: str) -> str:
    return (
        f"Lee la transcripcion completa de esta clase del ramo {ramo} y extrae lo "
        f"que el profesor pidio: {ruta_transcripcion}\n\n"
        "Cuando termines, la ultima linea de tu respuesta debe ser exactamente "
        "esta, sin nada mas en esa linea y con JSON valido en una sola linea:\n"
        'RESULTADO_LLAMADOS: {"avisos": [{"que": "<que hay que hacer>", '
        '"cuando": "<como lo dijo el profe, o cadena vacia>", '
        '"textual": "<frase textual>", "seguro": true}], '
        '"evaluacion": [{"tema": "<que entra>", "textual": "<frase textual>", '
        '"seguro": true}]}'
    )


def _parsear(texto: str) -> dict | None:
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea.startswith(MARCADOR_LLAMADOS):
            continue
        try:
            datos = json.loads(linea[len(MARCADOR_LLAMADOS):].strip())
        except json.JSONDecodeError:
            return None
        for clave in ("avisos", "evaluacion"):
            if not isinstance(datos.get(clave), list):
                datos[clave] = []
        return datos
    return None


async def extraer_llamados(ruta_transcripcion: str, ramo: str, slug: str) -> dict | None:
    """
    Devuelve {"avisos": [...], "evaluacion": [...]}, o None si no se pudo
    averiguar. Nunca revienta: una clase no se pierde por esto.

    Esa diferencia entre "no anuncio nada" y "no pude averiguarlo" antes no
    existia, y esa era justamente la falla. Dos listas vacias son una respuesta
    legitima y frecuente, el profesor no dijo nada. Pero cuando la llamada
    fallaba (un 429, o una respuesta sin la linea RESULTADO_LLAMADOS) esto
    devolvia tambien dos listas vacias, indistinguibles de la respuesta buena.

    Y quien llama las guardaba en el _skill.json. Como la condicion para
    reintentar es que el campo no exista, ya no se reintentaba nunca: un corte
    de red quedaba congelado como "el profesor no pidio nada", en la seccion
    que va primera en el documento y que el estudiante cree sin dudar (fechas
    de prueba, entregas, que entra en la evaluacion). Perder la seccion es
    mucho menos grave que afirmar en falso que esta vacia.
    """
    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        setting_sources=[],
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["Read"],
        disallowed_tools=["Bash", "Write", "Edit", "NotebookEdit"],
        permission_mode="bypassPermissions",
        hooks={
            "PreToolUse": [
                # Solo el proyecto: esta etapa lee la transcripcion y nada mas,
                # asi que el vault no tiene por que estar a su alcance.
                HookMatcher(
                    matcher="Read",
                    hooks=[construir_gate_de_rutas(PROJECT_ROOT)],
                )
            ]
        },
        cli_path=str(CLI_PATH),
        max_turns=MAX_TURNS,
    )

    partes = []
    error_sdk = None
    async for mensaje in query(
        prompt=_construir_prompt(ruta_transcripcion, ramo), options=options
    ):
        if isinstance(mensaje, AssistantMessage):
            for bloque in mensaje.content:
                if isinstance(bloque, TextBlock):
                    partes.append(bloque.text)
        elif isinstance(mensaje, ResultMessage):
            registrar_uso("llamados", slug, mensaje)
            if mensaje.is_error:
                error_sdk = describir_error_sdk(mensaje)

    datos = _parsear("\n".join(partes))
    if datos is None:
        motivo = (
            f"hubo un problema de conexion ({error_sdk})" if error_sdk
            else "el modelo no devolvio la lista"
        )
        notificar_aviso(
            "No se pudo leer lo que pidio el profesor",
            f"{ramo}: {motivo}. El documento se arma sin esa seccion, y se "
            "vuelve a intentar la proxima vez que regeneres esta clase. Ojo: "
            "que la seccion falte no significa que el profesor no anunciara "
            "nada, significa que no se pudo comprobar.",
        )
    return datos


def _leer_nota(ruta: str | None, vault_dir: str) -> str:
    """
    Una sola implementacion, la de finalizar_clase, que es donde esta escrito
    por que existe: acota la lectura al vault para que una ruta colada en la
    transcripcion no pueda meter cualquier archivo del disco en el .docx y en
    las flashcards. Aqui habia una copia equivalente, y duplicar una
    comprobacion de seguridad garantiza que algun dia una de las dos se
    endurezca y la otra se quede atras sin que nadie lo note.

    El import va dentro de la funcion, como el de _revisar_y_corregir mas
    abajo, para no crear una dependencia de modulo entre estos dos.
    """
    from .finalizar_clase import _leer_nota as leer

    return leer(ruta, vault_dir)


async def regenerar(slug: str, config: dict, sufijo: str = " (diseño nuevo)") -> Path:
    """
    Rehace el documento de una clase. Con `sufijo` vacio pisa el documento
    original, que es lo que se querria despues de comprobar que el diseño
    nuevo convence.
    """
    ruta_meta = dir_pendientes() / f"{slug}.json"
    ruta_skill = dir_pendientes() / f"{slug}_skill.json"
    if not ruta_meta.is_file() or not ruta_skill.is_file():
        raise FileNotFoundError(
            f"Falta {ruta_meta.name} o {ruta_skill.name}. Esa clase no esta procesada."
        )

    trabajo = json.loads(ruta_meta.read_text(encoding="utf-8"))
    # Este _skill.json puede venir de una corrida vieja, de antes de que el
    # titulo tuviera respaldo garantizado (ver normalizar_resultado). Regenerar
    # una clase asi no puede reventar por el nombre del documento.
    resultado = normalizar_resultado(
        json.loads(ruta_skill.read_text(encoding="utf-8")), trabajo["ramo"]
    )
    vault_dir = config["rutas"]["vault_obsidian"]

    llamados = resultado.get("llamados")
    if llamados is None:
        print("  extrayendo los llamados a la accion de la transcripcion...")
        extraidos = await extraer_llamados(trabajo["archivo_texto"], trabajo["ramo"], slug)
        if extraidos is None:
            # No se guarda a proposito. Cachear un vacio que no se pudo
            # comprobar dejaria la clase afirmando "el profesor no pidio nada"
            # para siempre, porque la condicion de arriba ya no volveria a ser
            # verdadera (ver extraer_llamados). Sin guardar, el documento sale
            # ahora sin la seccion y la proxima regeneracion lo reintenta.
            llamados = {"avisos": [], "evaluacion": []}
        else:
            llamados = extraidos
            # Se guardan para que la proxima regeneracion de esta clase no vuelva a
            # pagar la lectura de la transcripcion.
            resultado["llamados"] = llamados
            ruta_skill.write_text(
                json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    titulo = resultado["titulo"]
    trabajo["archivos"] = trabajo.get("archivos_originales", [])

    destino = None
    if sufijo:
        base = nombre_base(trabajo["numero_clase"], trabajo["fecha"], titulo)
        destino = Path(config["rutas"]["output"]) / trabajo["ramo"] / f"{base}{sufijo}.docx"

    return generar_docx(
        trabajo,
        titulo,
        _leer_nota(resultado.get("fuente"), vault_dir),
        _leer_nota(resultado.get("aprendizaje"), vault_dir),
        resultado.get("conceptos_repetidos") or [],
        config,
        _leer_nota(resultado.get("contexto"), vault_dir),
        llamados,
        destino,
    )


AUTORIZACION_SOBRESCRITURA = (
    "Esta clase ya se proceso antes y sus notas existen en esa carpeta. Vas a "
    "rehacerlas con el formato actual, asi que **estas autorizado a sobrescribir "
    "tus propias notas anteriores de esta misma clase** sin pedir confirmacion: "
    "ya hay un respaldo. Esa autorizacion vale solo para las notas de esta clase "
    "(fuente, aprendizaje y contexto). No toques ninguna otra nota del vault.\n\n"
    "Las notas viejas tienen la estructura anterior, con los pasos 1, 2 y 5 del "
    "metodo separados y el desarrollo de la clase repetido en la nota de fuente. "
    "No las copies: escribe la version nueva desde la transcripcion, con la "
    "materia en una sola seccion desarrollada que incluya los casos y ejemplos "
    "del profesor. El documento de estudio tiene que bastarse solo."
)

RESPALDO_DIR = Path(__file__).parent / "respaldo_notas"


def _respaldar_notas(resultado: dict, slug: str) -> Path | None:
    """
    Copia las notas actuales antes de que la skill las pise.

    Rehacer una clase es la unica operacion de este repo que destruye trabajo
    ya hecho, y las notas no se reconstruyen solas si el resultado nuevo sale
    peor. El respaldo queda fuera del vault para no ensuciarlo con archivos que
    despues aparecen en las busquedas de Obsidian.
    """
    from datetime import datetime

    destino = RESPALDO_DIR / f"{slug}_{datetime.now():%Y%m%d_%H%M%S}"
    copiadas = 0
    for clave in ("fuente", "aprendizaje", "contexto"):
        origen = resultado.get(clave)
        if not origen or not Path(origen).is_file():
            continue
        destino.mkdir(parents=True, exist_ok=True)
        (destino / Path(origen).name).write_text(
            Path(origen).read_text(encoding="utf-8"), encoding="utf-8"
        )
        copiadas += 1
    return destino if copiadas else None


async def rehacer(slug: str, config: dict, sufijo: str = " (diseño nuevo)") -> Path:
    """
    Vuelve a analizar la clase entera con la skill actual y rehace el
    documento. Es lo caro: paga otra vez el destilado y la revision.

    Se usa cuando el cambio no es de presentacion sino de que contiene el
    material. Regenerar solo redibuja lo que ya estaba escrito, asi que no
    puede recuperar, por ejemplo, los casos del profesor que la version
    anterior de la skill dejaba fuera de la seccion de estudio.
    """
    from .carpetas import resolver_carpeta_ramo
    from .config import guardar_config
    from .finalizar_clase import _revisar_y_corregir
    from .skill_runner import aplicar_skill

    ruta_meta = dir_pendientes() / f"{slug}.json"
    ruta_skill = dir_pendientes() / f"{slug}_skill.json"
    trabajo = json.loads(ruta_meta.read_text(encoding="utf-8"))
    anterior = json.loads(ruta_skill.read_text(encoding="utf-8"))
    vault_dir = config["rutas"]["vault_obsidian"]

    respaldo = _respaldar_notas(anterior, slug)
    print(f"  respaldo de las notas actuales: {respaldo}")

    carpeta_ramo, cambio = resolver_carpeta_ramo(trabajo["ramo"], vault_dir, config)
    if cambio:
        guardar_config(config)

    print("  reanalizando la clase con la skill actual...")
    resultado = await aplicar_skill(
        trabajo["archivo_texto"], trabajo["ramo"], vault_dir, slug,
        str(carpeta_ramo), AUTORIZACION_SOBRESCRITURA,
    )

    print("  revisando lo escrito contra la transcripcion...")
    resultado = await _revisar_y_corregir(
        trabajo["archivo_texto"], resultado, trabajo["ramo"], vault_dir, slug
    )

    # La skill nueva ya reporta los llamados; si no lo hizo, se conservan los
    # que ya se habian extraido antes en vez de perderlos.
    if not resultado.get("llamados") and anterior.get("llamados"):
        resultado["llamados"] = anterior["llamados"]
    ruta_skill.write_text(
        json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return await regenerar(slug, config, sufijo)


if __name__ == "__main__":
    import sys

    import anyio

    if len(sys.argv) < 2:
        disponibles = sorted(
            p.stem.replace("_skill", "") for p in dir_pendientes().glob("*_skill.json")
        )
        print("Uso: python3 -m orquestador.regenerar <slug> [<slug>...] [--pisar] [--rehacer]")
        print("\n  (sin banderas)  redibuja el documento con las notas que ya existen")
        print("  --rehacer       vuelve a analizar la clase entera con la skill actual")
        print("                  (cuesta como procesar la clase de nuevo, y reescribe")
        print("                   las notas del vault dejando respaldo)")
        print("  --pisar         reemplaza el documento existente en vez de crear una copia")
        print("\nClases procesadas disponibles:")
        for s in disponibles:
            print(f"  {s}")
        raise SystemExit(1)

    pisar = "--pisar" in sys.argv
    rehacer_todo = "--rehacer" in sys.argv
    slugs = [a for a in sys.argv[1:] if not a.startswith("--")]
    _config = cargar_config()

    for _slug in slugs:
        print(f"\n{_slug}")
        _fn = rehacer if rehacer_todo else regenerar
        _ruta = anyio.run(_fn, _slug, _config, "" if pisar else " (diseño nuevo)")
        print(f"  -> {_ruta}")

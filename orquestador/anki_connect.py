"""
Cliente minimo de AnkiConnect (protocolo version 6). Requiere que Anki este
abierto y tenga el addon AnkiConnect instalado (codigo 2055492159, Herramientas
-> Complementos -> Obtener complementos). Si Anki no esta abierto, las
funciones de aca lanzan ConnectionError con un mensaje claro, para que quien
llame decida si continuar sin Anki en vez de abortar todo el proceso.
"""
import requests

URL = "http://127.0.0.1:8765"
VERSION = 6


def _llamar(action: str, **params):
    try:
        resp = requests.post(URL, json={"action": action, "version": VERSION, "params": params}, timeout=5)
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(
            "No se pudo conectar a AnkiConnect en localhost:8765. "
            "Verifica que Anki este abierto y el addon AnkiConnect instalado."
        ) from e
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise RuntimeError(f"AnkiConnect devolvio un error en '{action}': {data['error']}")
    return data.get("result")


def verificar_conexion() -> bool:
    try:
        _llamar("version")
        return True
    except ConnectionError:
        return False


def crear_mazo_si_no_existe(nombre_mazo: str) -> None:
    _llamar("createDeck", deck=nombre_mazo)


# El Anki del estudiante esta en espanol: el modelo basico se llama "Básico" y sus
# campos son "Anverso"/"Reverso", no "Basic"/"Front"/"Back" (verificado en vivo
# contra su Anki real con modelNames/modelFieldNames).
MODELO_BASICO = "Básico"
CAMPO_ANVERSO = "Anverso"
CAMPO_REVERSO = "Reverso"


def borrar_notas(ids: list[int]) -> None:
    """
    Quita tarjetas por su id. Lo usa el aborto para dejar Anki como estaba
    (ver bitacora.py): agregar_flashcards devuelve el id de cada tarjeta que
    creo, y esos ids son lo unico que permite deshacerlo despues, porque una
    tarjeta ya agregada no se distingue de las que el estudiante tenia.
    """
    if ids:
        _llamar("deleteNotes", notes=list(ids))


def agregar_flashcards(mazo: str, tarjetas: list[tuple[str, str]], tags: list[str] | None = None) -> list[int | None]:
    """
    Agrega las tarjetas de a una (no en un solo lote): verificado en vivo que
    si un lote de addNotes trae aunque sea una tarjeta duplicada, AnkiConnect
    rechaza el lote COMPLETO con error (no agrega ninguna, ni siquiera las
    que si eran nuevas). De a una, un duplicado solo se salta a si mismo.
    """
    resultados = []
    for pregunta, respuesta in tarjetas:
        note = {
            "deckName": mazo,
            "modelName": MODELO_BASICO,
            "fields": {CAMPO_ANVERSO: pregunta, CAMPO_REVERSO: respuesta},
            "tags": tags or [],
            "options": {"allowDuplicate": False, "duplicateScope": "deck"},
        }
        try:
            resultado = _llamar("addNotes", notes=[note])
            resultados.append(resultado[0] if resultado else None)
        except RuntimeError as e:
            if "duplicate" in str(e).lower():
                resultados.append(None)
            else:
                raise
    return resultados

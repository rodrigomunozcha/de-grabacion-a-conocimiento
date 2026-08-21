"""
Registro del consumo de cada llamada al SDK, una linea JSON por corrida, en
logs/uso.jsonl.

Existe porque el costo de este pipeline no se puede estimar bien desde
afuera: depende del largo de la transcripcion, de cuanto explora la skill el
vault antes de escribir, y de si el revisor encontro algo que corregir. Con
este registro, despues de unas cuantas clases hay numeros reales en vez de
suposiciones (ver `python3 -m orquestador.uso`).

Sobre `costo_usd_estimado`: viene de `total_cost_usd` del SDK y es una
estimacion del lado del cliente de lo que costaria por API. Con plan Pro no
se paga eso, se consume cuota. Sirve para comparar etapas entre si (cual
sale caro), no como factura.
"""
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path(__file__).parent / "logs"
RUTA_USO = LOGS_DIR / "uso.jsonl"


def registrar_uso(etapa: str, slug: str, mensaje_resultado) -> None:
    """Anota lo que consumio una corrida del SDK. Nunca revienta el pipeline:
    si el registro falla, la clase igual se termina de procesar."""
    try:
        uso = mensaje_resultado.usage or {}
        linea = {
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "etapa": etapa,
            "slug": slug,
            "turnos": mensaje_resultado.num_turns,
            "duracion_s": round(mensaje_resultado.duration_ms / 1000),
            "input": uso.get("input_tokens"),
            "output": uso.get("output_tokens"),
            "cache_creacion": uso.get("cache_creation_input_tokens"),
            "cache_lectura": uso.get("cache_read_input_tokens"),
            "costo_usd_estimado": mensaje_resultado.total_cost_usd,
            # Sin esto no se puede saber por que fallo una corrida cara: un
            # fallo HTTP de la API llega con subtype "success" y el codigo real
            # solo esta aqui (ver skill_runner.describir_error_sdk).
            "error_api": getattr(mensaje_resultado, "api_error_status", None),
            "termino_por": getattr(mensaje_resultado, "terminal_reason", None),
        }
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(RUTA_USO, "a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
    except Exception:
        pass


def registrar_transcripcion(slug: str, duracion_audio_s: float, duracion_real_s: float) -> None:
    """
    Anota cuanto se demoro en transcribir y cuanto duraba el audio, para poder
    estimar la proxima vez con datos propios.

    Existe porque la primera version estimaba con una velocidad fija escrita a
    mano, y esa constante estaba mal: se calibro suponiendo la duracion de un
    audio en vez de medirla. En una clase real la estimacion se quedo corta por
    un factor de tres y el icono decia "ya se paso de lo habitual" cuando en
    realidad todo iba bien. Una estimacion inventada es peor que no dar
    ninguna, porque preocupa sin motivo.

    La velocidad ademas no es una sola: depende del audio. Whisper reintenta
    los tramos donde tiene poca confianza, asi que una grabacion con peor
    sonido puede tardar varias veces mas con el mismo modelo. Por eso se
    guarda cada corrida y despues se usa la mas lenta de las recientes.
    """
    if not duracion_audio_s or not duracion_real_s:
        return
    try:
        linea = {
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "etapa": "transcripcion",
            "slug": slug,
            "duracion_s": round(duracion_real_s),
            "audio_s": round(duracion_audio_s),
            "velocidad": round(duracion_audio_s / duracion_real_s, 2),
        }
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(RUTA_USO, "a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
    except Exception:
        pass


def resumen() -> str:
    """Promedios por etapa, para saber cuanto cuesta de verdad cada parte."""
    if not RUTA_USO.exists():
        return "Todavia no hay corridas registradas en logs/uso.jsonl."

    por_etapa = defaultdict(list)
    for linea in RUTA_USO.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            registro = json.loads(linea)
        except json.JSONDecodeError:
            continue
        por_etapa[registro.get("etapa", "?")].append(registro)

    filas = ["etapa            corridas  input   cache_lec  output  turnos  costo_est"]
    for etapa, registros in sorted(por_etapa.items()):
        n = len(registros)

        def prom(campo):
            valores = [r.get(campo) or 0 for r in registros]
            return sum(valores) / n

        filas.append(
            f"{etapa:<16} {n:>8}  {prom('input'):>6.0f}  {prom('cache_lectura'):>9.0f}  "
            f"{prom('output'):>6.0f}  {prom('turnos'):>6.1f}  {prom('costo_usd_estimado'):>8.3f}"
        )
    filas.append("")
    filas.append("Promedios por corrida. 'cache_lec' son tokens de contexto releido")
    filas.append("desde cache (se cobran a una fraccion del input normal).")
    return "\n".join(filas)


if __name__ == "__main__":
    print(resumen())

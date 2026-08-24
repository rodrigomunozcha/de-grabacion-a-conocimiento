"""
Revision de salud del sistema: comprueba que todo lo que el pipeline necesita
siga en su lugar y funcionando.

Por que existe. El sistema se apoya en herramientas que se actualizan solas o
por fuera (ffmpeg y terminal-notifier vienen de Homebrew, el CLI de Claude Code
de npm, Whisper y el resto de pip). Una actualizacion puede romper algo sin que
nadie se entere hasta la proxima clase, que es el peor momento para descubrirlo.

Ya paso: una actualizacion de Homebrew dejo terminal-notifier sin poder
entregar avisos, y como el codigo no miraba el resultado, las notificaciones
habrian desaparecido en silencio.

No cuesta tokens: no llama al modelo, solo comprueba que las piezas esten y
respondan. Correr despues de cada `brew upgrade`, `npm update` o actualizacion
de macOS:

    python3 -m orquestador.verificar
"""
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent

OK, AVISO, FALLA = "OK   ", "AVISO", "FALLA"

_resultados: list[tuple[str, str, str]] = []


def _anotar(estado: str, que: str, detalle: str = "") -> None:
    _resultados.append((estado, que, detalle))
    linea = f"  {estado}  {que}"
    print(f"{linea}\n         {detalle}" if detalle else linea)


def _comando(nombre: str, argumentos: list[str], obligatorio: bool = True) -> None:
    ruta = shutil.which(nombre)
    if not ruta:
        _anotar(FALLA if obligatorio else AVISO, f"{nombre} no esta instalado",
                "se instala con: brew install " + nombre)
        return
    try:
        salida = subprocess.run([ruta] + argumentos, capture_output=True, text=True, timeout=20)
        version = (salida.stdout or salida.stderr).splitlines()[0][:52]
        _anotar(OK, f"{nombre}", version)
    except Exception as e:
        _anotar(FALLA, f"{nombre} no responde", f"{type(e).__name__}")


def _paquetes_python() -> None:
    import importlib

    for modulo, para_que in [
        ("claude_agent_sdk", "hablar con el modelo"),
        ("mlx_whisper", "transcribir"),
        ("docx", "armar el .docx"),
        ("matplotlib", "dibujar formulas y mapas"),
        ("PIL", "medir las imagenes"),
        ("requests", "hablar con Anki"),
        ("anyio", "correr las etapas"),
    ]:
        try:
            importlib.import_module(modulo)
            _anotar(OK, f"paquete {modulo}")
        except Exception:
            _anotar(FALLA, f"falta el paquete {modulo}", f"hace falta para {para_que}")


def _modulos_del_pipeline() -> None:
    import importlib
    import pkgutil

    import orquestador

    fallaron = []
    nombres = [m.name for m in pkgutil.iter_modules(orquestador.__path__)]
    for nombre in nombres:
        try:
            importlib.import_module(f"orquestador.{nombre}")
        except Exception as e:
            fallaron.append(f"{nombre} ({type(e).__name__})")
    if fallaron:
        _anotar(FALLA, "hay modulos del pipeline que no cargan", ", ".join(fallaron))
    else:
        _anotar(OK, f"los {len(nombres)} modulos del pipeline cargan")


def _notificaciones() -> None:
    """Se prueba de verdad, no solo que el programa exista: el fallo que ya
    ocurrio fue justamente uno donde el binario estaba pero no entregaba."""
    from .notificaciones import _con_applescript, _con_terminal_notifier

    if _con_terminal_notifier("Revision del sistema", "", "Las notificaciones funcionan.",
                              None, False):
        _anotar(OK, "notificaciones", "por terminal-notifier, con clic para abrir")
        return
    try:
        _con_applescript("Revision del sistema", "", "Las notificaciones funcionan (via de respaldo).")
        _anotar(AVISO, "notificaciones por la via de respaldo",
                "terminal-notifier no entrega; llegan igual, pero sin clic para abrir")
    except Exception:
        _anotar(FALLA, "no se pueden entregar notificaciones",
                "el procesamiento igual funciona; revisa Estado.txt para ver el avance")


def _configuracion() -> None:
    from .config import CONFIG_PATH, cargar_config

    if not CONFIG_PATH.exists():
        _anotar(FALLA, "falta config.json", "corre el asistente: Configurar Sistema.app")
        return
    try:
        config = cargar_config()
    except Exception as e:
        _anotar(FALLA, "config.json no se puede leer", f"{type(e).__name__}")
        return

    _anotar(OK, "config.json")
    for clave, ruta in config.get("rutas", {}).items():
        destino = Path(ruta).expanduser()
        if destino.exists():
            _anotar(OK, f"carpeta {clave}")
        else:
            _anotar(FALLA, f"la carpeta {clave} ya no existe", str(destino))

    transcriptotem = Path(config["rutas"]["transcriptotem"]).expanduser()
    if not (transcriptotem / "backend" / "transcriber.py").exists():
        _anotar(FALLA, "no encuentro el transcriptor",
                f"falta backend/transcriber.py en {transcriptotem}")


def _cli_de_claude() -> None:
    cli = RAIZ / "node_modules" / ".bin" / "claude"
    if not cli.exists():
        _anotar(FALLA, "falta el CLI de Claude Code", "se reinstala con: npm install")
        return
    try:
        salida = subprocess.run([str(cli), "--version"], capture_output=True, text=True, timeout=60)
        _anotar(OK, "CLI de Claude Code", salida.stdout.strip()[:52])
    except Exception as e:
        _anotar(FALLA, "el CLI de Claude Code no responde", f"{type(e).__name__}")


def _anki() -> None:
    from . import anki_connect

    if anki_connect.verificar_conexion():
        _anotar(OK, "Anki", "abierto y con AnkiConnect respondiendo")
    else:
        _anotar(AVISO, "Anki cerrado",
                "no es un error: las clases se procesan igual, sin flashcards")


def _icono_de_la_barra() -> None:
    binario = RAIZ / "barra_menu" / "BarraEstado"
    if binario.exists():
        _anotar(OK, "icono de la barra de menu")
    else:
        _anotar(AVISO, "falta el icono de la barra",
                "se compila con: bash boton_app/compilar_apps.sh")


def main() -> int:
    print("\nRevision del sistema\n" + "=" * 58)

    print("\nHerramientas externas")
    _comando("ffmpeg", ["-version"])
    _comando("ffprobe", ["-version"])
    _comando("node", ["--version"])

    print("\nPaquetes de Python")
    _paquetes_python()

    print("\nEl pipeline")
    _modulos_del_pipeline()
    _cli_de_claude()
    _configuracion()

    print("\nLo que ves mientras trabaja")
    _notificaciones()
    _icono_de_la_barra()
    _anki()

    fallas = [r for r in _resultados if r[0] == FALLA]
    avisos = [r for r in _resultados if r[0] == AVISO]

    print("\n" + "=" * 58)
    if fallas:
        print(f"HAY {len(fallas)} PROBLEMA(S) QUE IMPIDEN PROCESAR CLASES:")
        for _, que, detalle in fallas:
            print(f"  - {que}" + (f": {detalle}" if detalle else ""))
        return 1
    if avisos:
        print(f"Todo lo esencial funciona. {len(avisos)} aviso(s) sin importancia:")
        for _, que, detalle in avisos:
            print(f"  - {que}")
        return 0
    print("Todo funciona. Puedes procesar clases con tranquilidad.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Notificaciones nativas de macOS al terminar de procesar una clase (exito o
error), con clic para abrir el resultado. Usa terminal-notifier (instalado
via Homebrew), porque las notificaciones nativas de AppleScript
("display notification") no soportan accion al hacer clic.

Cada notificacion tambien queda anotada en Estado.txt (en la raiz del
proyecto, junto a Input/Output/Procesados), por si el estudiante no alcanza a ver
la notificacion o quiere confirmar que no quedo pegado: puede abrir ese
archivo en cualquier momento (doble clic, se abre en TextEdit) y ver la
ultima actividad, sin depender de Terminal ni de la notificacion misma.
"""
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path

from . import estado_vivo

TERMINAL_NOTIFIER = "/opt/homebrew/bin/terminal-notifier"
LOGS_DIR = Path(__file__).parent / "logs"
ESTADO_PATH = Path(__file__).parent.parent / "Estado.txt"
LINEAS_MAXIMAS_ESTADO = 200


def _file_url(ruta: Path) -> str:
    return "file://" + urllib.parse.quote(str(ruta.resolve()))


def _anotar_estado(linea: str) -> None:
    marca = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    existentes = ESTADO_PATH.read_text(encoding="utf-8").splitlines() if ESTADO_PATH.exists() else []
    existentes.append(f"[{marca}] {linea}")
    ESTADO_PATH.write_text("\n".join(existentes[-LINEAS_MAXIMAS_ESTADO:]) + "\n", encoding="utf-8")


def _notificar(
    titulo: str, subtitulo: str, mensaje: str, url_al_hacer_clic: str | None = None, sonido: bool = True
) -> None:
    partes = [p for p in (titulo, subtitulo, mensaje) if p]
    _anotar_estado(" - ".join(partes))

    # Entregar el aviso va dentro de un try propio: el estado ya quedo escrito
    # arriba, y ninguna falla avisando puede costarle la clase al estudiante.
    try:
        if _con_terminal_notifier(titulo, subtitulo, mensaje, url_al_hacer_clic, sonido):
            return
        _con_applescript(titulo, subtitulo, mensaje)
    except Exception:
        pass


def _con_terminal_notifier(
    titulo: str, subtitulo: str, mensaje: str, url_al_hacer_clic: str | None, sonido: bool
) -> bool:
    """
    Via preferida: es la unica que permite abrir el .docx al hacer clic en el
    aviso. Devuelve False si no se pudo entregar.
    """
    if not Path(TERMINAL_NOTIFIER).exists():
        return False
    comando = [
        TERMINAL_NOTIFIER,
        "-title", titulo,
        "-subtitle", subtitulo,
        "-message", mensaje,
        "-group", "orquestador-estudio",
    ]
    if sonido:
        comando += ["-sound", "default"]
    if url_al_hacer_clic:
        comando += ["-open", url_al_hacer_clic]
    try:
        return subprocess.run(comando, capture_output=True, text=True).returncode == 0
    except Exception:
        return False


def _con_applescript(titulo: str, subtitulo: str, mensaje: str) -> None:
    """
    Respaldo cuando terminal-notifier no puede entregar el aviso.

    Existe porque una actualizacion de Homebrew lo dejo de golpe sin funcionar:
    la version 3.0.0 pide permiso de notificaciones por una via que exige un
    binario firmado, y el de Homebrew no lo esta, asi que falla con
    "UNErrorDomain error 1". Peor todavia, el codigo no miraba el resultado, de
    modo que el estudiante habria dejado de recibir avisos sin enterarse: el
    procesamiento seguiria funcionando y el aviso simplemente no llegaria.

    No reemplaza a terminal-notifier: por esta via el aviso no se puede abrir
    con un clic. Pero avisar sin poder hacer clic es muchisimo mejor que no
    avisar. La ruta al documento igual queda en Estado.txt.
    """
    partes = [p for p in (subtitulo, mensaje) if p]
    cuerpo = " - ".join(partes) or titulo
    guion = (
        f"display notification {_escapar_applescript(cuerpo)} "
        f"with title {_escapar_applescript(titulo)}"
    )
    try:
        subprocess.run(["osascript", "-e", guion], capture_output=True, text=True)
    except Exception:
        pass  # ya quedo en Estado.txt; un aviso no puede tumbar una clase


def _escapar_applescript(texto: str) -> str:
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"') + '"'


def notificar_inicio(cantidad: int) -> None:
    plural = "grabación" if cantidad == 1 else "grabaciones"
    _notificar(
        titulo="Procesando clases",
        subtitulo=f"{cantidad} {plural} en Input",
        mensaje="Esto puede tardar unos minutos. Te aviso cuando termine cada una.",
    )


def notificar_progreso(etapa: str, detalle: str = "", eta_segundos: float | None = None,
                       sub: tuple[int, int] | None = None) -> None:
    """Aviso intermedio mientras avanza el procesamiento (transcribiendo,
    aplicando la skill). Mismo grupo que el resto: reemplaza al aviso
    anterior en el Centro de Notificaciones en vez de amontonarse, y sin
    sonido para no interrumpir con cada paso.

    Ademas actualiza el estado que lee el icono de la barra de menu. Se hace
    aca y no con una llamada aparte en cada etapa para que no puedan quedar
    desincronizados: toda etapa que ya avisaba, ahora tambien aparece en la
    barra, sin tener que acordarse de agregarla en dos lugares."""
    estado_vivo.paso(etapa, detalle, eta_segundos, sub)
    _notificar(titulo="Procesando...", subtitulo=etapa, mensaje=detalle, sonido=False)


def notificar_exito(trabajo: dict, titulo_clase: str, ruta_docx: Path) -> None:
    _notificar(
        titulo="Clase procesada",
        subtitulo=f"{trabajo['ramo']} - {trabajo['fecha']}",
        mensaje=titulo_clase,
        url_al_hacer_clic=_file_url(ruta_docx),
    )


def notificar_aviso(titulo: str, mensaje: str) -> None:
    """Para avisos que no son error ni exito completo (ej. Anki cerrado)."""
    _notificar(titulo=titulo, subtitulo="", mensaje=mensaje)


def notificar_error(contexto: str, detalle: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ruta_log = LOGS_DIR / "errores.log"
    with open(ruta_log, "a", encoding="utf-8") as f:
        f.write(f"=== {contexto} ===\n{detalle}\n\n")

    _notificar(
        titulo="Error procesando una clase",
        subtitulo=contexto,
        mensaje="Toca para ver el detalle del error.",
        url_al_hacer_clic=_file_url(ruta_log),
    )

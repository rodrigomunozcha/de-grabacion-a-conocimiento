"""
Registro de todo lo que una corrida cambia en el disco, para poder devolverlo
exactamente a como estaba si el estudiante decide abortar.

Por que existe. Detener el procesamiento a mitad de camino no sirve de nada si
deja restos: media nota en el vault, el audio movido a Procesados, tarjetas
sueltas en Anki. El estudiante tendria que salir a limpiar a mano justo cuando
lo que queria era cancelar. "Abortar" solo es util si significa que no paso
nada.

Como funciona. Cada etapa anota aca lo que va a cambiar, ANTES de cambiarlo, y
el registro se guarda en disco en cada anotacion. Eso ultimo es lo que lo hace
confiable: si el proceso muere de golpe (un corte inmediato es justamente eso),
el registro en disco ya refleja lo que alcanzo a pasar, y deshacer sigue siendo
posible desde afuera.

Lo unico que NO se deshace son los registros de actividad (Estado.txt, los logs
y el registro de uso). Son la constancia de que hubo una corrida y de que se
aborto: borrarlos seria esconder lo que paso, no restaurar nada.

El orden importa. Al deshacer se recorre al reves, porque los cambios se
encadenan: la carpeta del ramo solo se puede borrar despues de borrar las notas
que se escribieron dentro.
"""
import json
import shutil
from datetime import datetime
from pathlib import Path

RUTA_POR_DEFECTO = Path(__file__).parent / "bitacora_actual.json"
RESPALDOS_DIR = Path(__file__).parent / "respaldos_bitacora"

# Tipos de cambio registrables.
ARCHIVO_CREADO = "archivo_creado"
ARCHIVO_MODIFICADO = "archivo_modificado"
CARPETA_CREADA = "carpeta_creada"
AUDIO_MOVIDO = "audio_movido"
NOTAS_ANKI = "notas_anki"


class Bitacora:
    def __init__(self, ruta: Path | None = None):
        self.ruta = Path(ruta) if ruta else RUTA_POR_DEFECTO
        self.cambios: list[dict] = []
        self._respaldos = RESPALDOS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")

    # ---- anotar ----

    def _anotar(self, cambio: dict) -> None:
        self.cambios.append(cambio)
        self._guardar()

    def archivo_creado(self, ruta: str | Path) -> None:
        self._anotar({"tipo": ARCHIVO_CREADO, "ruta": str(ruta)})

    def carpeta_creada(self, ruta: str | Path) -> None:
        self._anotar({"tipo": CARPETA_CREADA, "ruta": str(ruta)})

    def audio_movido(self, origen: str | Path, destino: str | Path) -> None:
        self._anotar({"tipo": AUDIO_MOVIDO, "origen": str(origen), "destino": str(destino)})

    def notas_anki(self, ids: list) -> None:
        limpios = [i for i in ids if i]
        if limpios:
            self._anotar({"tipo": NOTAS_ANKI, "ids": limpios})

    def respaldar(self, ruta: str | Path) -> None:
        """
        Guarda una copia de un archivo que ya existia y que algo va a modificar.

        Es el unico cambio que no se puede deshacer sin preparacion: una nota
        que la skill edita (tipicamente el indice del ramo) no se reconstruye
        sola. Si el archivo no existe todavia, no hay nada que respaldar y se
        anota como creado.
        """
        ruta = Path(ruta)
        if not ruta.is_file():
            self.archivo_creado(ruta)
            return
        self._respaldos.mkdir(parents=True, exist_ok=True)
        copia = self._respaldos / f"{len(self.cambios):03d}-{ruta.name}"
        shutil.copy2(ruta, copia)
        self._anotar({"tipo": ARCHIVO_MODIFICADO, "ruta": str(ruta), "respaldo": str(copia)})

    def fotografiar_carpeta(self, carpeta: str | Path) -> None:
        """
        Deja constancia de como estaba una carpeta antes de que la skill
        escribiera en ella: respalda lo que ya habia y anota la carpeta misma
        si todavia no existia.

        Se hace por carpeta y no archivo por archivo porque quien escribe es el
        modelo, no nosotros: no sabemos de antemano cuantas notas va a crear ni
        cuales va a tocar. Lo que si sabemos es donde. Al deshacer, todo lo que
        aparezca ahi y no estuviera en la foto se borra.
        """
        carpeta = Path(carpeta)
        if not carpeta.is_dir():
            self.carpeta_creada(carpeta)
            return
        for archivo in sorted(carpeta.glob("*.md")):
            self.respaldar(archivo)
        self._anotar({
            "tipo": "foto_carpeta",
            "ruta": str(carpeta),
            "archivos": sorted(p.name for p in carpeta.iterdir() if p.is_file()),
        })

    # ---- deshacer ----

    def deshacer(self) -> list[str]:
        """Devuelve la lista de lo que se revirtio, en lenguaje entendible."""
        hecho = []
        for cambio in reversed(self.cambios):
            try:
                hecho.extend(self._deshacer_uno(cambio))
            except Exception as e:
                hecho.append(f"No se pudo revertir {cambio.get('tipo')}: {type(e).__name__}")
        self.limpiar()
        return hecho

    def _deshacer_uno(self, cambio: dict) -> list[str]:
        tipo = cambio["tipo"]

        if tipo == ARCHIVO_CREADO:
            ruta = Path(cambio["ruta"])
            if ruta.is_file():
                ruta.unlink()
                return [f"Se borro el archivo {ruta.name}"]
            return []

        if tipo == ARCHIVO_MODIFICADO:
            respaldo = Path(cambio["respaldo"])
            if respaldo.is_file():
                shutil.copy2(respaldo, cambio["ruta"])
                return [f"Se restauro {Path(cambio['ruta']).name} como estaba"]
            return []

        if tipo == "foto_carpeta":
            carpeta = Path(cambio["ruta"])
            if not carpeta.is_dir():
                return []
            previos = set(cambio.get("archivos", []))
            borrados = []
            for archivo in carpeta.iterdir():
                if archivo.is_file() and archivo.name not in previos:
                    archivo.unlink()
                    borrados.append(archivo.name)
            return [f"Se borro la nota {n}" for n in borrados]

        if tipo == CARPETA_CREADA:
            carpeta = Path(cambio["ruta"])
            # Solo si quedo vacia: si tiene algo que no pusimos nosotros, se
            # respeta. Vale mas dejar una carpeta de mas que borrar algo ajeno.
            if carpeta.is_dir() and not any(carpeta.iterdir()):
                carpeta.rmdir()
                return [f"Se borro la carpeta {carpeta.name}"]
            return []

        if tipo == AUDIO_MOVIDO:
            destino, origen = Path(cambio["destino"]), Path(cambio["origen"])
            if destino.is_file() and not origen.exists():
                origen.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destino), str(origen))
                return [f"El audio volvio a {origen.parent.name}/"]
            return []

        if tipo == NOTAS_ANKI:
            from . import anki_connect
            if anki_connect.verificar_conexion():
                anki_connect.borrar_notas(cambio["ids"])
                return [f"Se quitaron {len(cambio['ids'])} tarjetas de Anki"]
            return ["Anki estaba cerrado: las tarjetas siguen ahi, hay que borrarlas a mano"]

        return []

    # ---- persistencia ----

    def _guardar(self) -> None:
        try:
            self.ruta.write_text(
                json.dumps(self.cambios, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass  # nunca puede tumbar el pipeline

    def limpiar(self) -> None:
        self.ruta.unlink(missing_ok=True)
        shutil.rmtree(self._respaldos, ignore_errors=True)

    @classmethod
    def cargar(cls, ruta: Path | None = None) -> "Bitacora":
        """Recupera una bitacora de una corrida anterior, para poder deshacerla
        desde afuera aunque el proceso que la escribio ya no exista."""
        b = cls(ruta)
        try:
            b.cambios = json.loads(b.ruta.read_text(encoding="utf-8"))
        except Exception:
            b.cambios = []
        return b


if __name__ == "__main__":
    # Permite deshacer a mano una corrida que quedo a medias, por ejemplo si el
    # Mac se apago en pleno procesamiento.
    b = Bitacora.cargar()
    if not b.cambios:
        print("No hay ninguna corrida a medio camino que deshacer.")
    else:
        print(f"Deshaciendo {len(b.cambios)} cambio(s):")
        for linea in b.deshacer():
            print(f"  - {linea}")

"""
Pruebas del orquestador que no cuestan tokens ni tocan nada real.

Cubren la logica determinista (fechas, nombres, flashcards, .docx) y, sobre
todo, las garantias de aislamiento del modo ensayo: que un ensayo no pueda
escribir en el vault real, en Anki, en config.json ni en la carpeta de
intermedios. Esa ultima garantia existe porque ya fallo una vez: un ensayo
dejaba <slug>_skill.json en la carpeta real y eso habria hecho que la
siguiente corrida de verdad se saltara la clase en silencio.

Correr con:
    python3 tests/test_orquestador.py
"""
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from orquestador import carpetas, deteccion, docx_generator, ensayo, extraer_flashcards, nombres
from orquestador.config import PENDIENTES_DIR_POR_DEFECTO, dir_pendientes, usar_dir_pendientes

fallos: list[str] = []


def check(nombre: str, cond: bool, detalle: str = "") -> None:
    print(("  OK   " if cond else "  FALLA") + f"  {nombre}" + (f"  <- {detalle}" if not cond and detalle else ""))
    if not cond:
        fallos.append(nombre)


def probar_nombres() -> None:
    print("\n== nombres ==")
    a = nombres.slug_pendiente("1970-01-20|a.m4a")
    b = nombres.slug_pendiente("1970-01-20|b.m4a")
    check("dos clases con la misma fecha corrupta no colisionan", a != b, f"{a} == {b}")
    check("el slug conserva la fecha legible", a.startswith("1970-01-20"))
    sucio = 'a/b:c*d?e"f<g>h|i'
    check("sanitiza caracteres ilegales de archivo",
          nombres.sanitizar_nombre_archivo(sucio) == "a-b-c-d-e-f-g-h-i")
    check("un titulo con .. no puede escapar de la carpeta",
          "/" not in nombres.sanitizar_nombre_archivo("../../etc/passwd"))
    check("numero de clase con cero a la izquierda",
          nombres.nombre_base(3, "2026-08-05", "Tema") == "Clase 03 - 2026-08-05 - Tema")


def probar_deteccion() -> None:
    print("\n== deteccion de fecha y ramo ==")
    check("rescata la fecha DD.MM.YY del nombre del archivo",
          deteccion._extraer_fecha_de_nombre("CAB7 10.04.25 Performance") == date(2025, 4, 10))
    check("ignora un nombre sin fecha",
          deteccion._extraer_fecha_de_nombre("grabacion final.m4a") is None)
    check("rechaza una fecha imposible", deteccion._extraer_fecha_de_nombre("x 32.13.25 y") is None)

    cfg = {"semestre": {"fecha_inicio": "2026-08-03"},
           "ramos": {"lunes": {"nombre": "R", "perfil_whisper": "es-chile"}}}
    check("una fecha anterior al semestre no asigna ramo (bug de 1970)",
          deteccion.resolver_ramo(date(1970, 1, 20), cfg) is None)
    check("un lunes dentro del semestre si asigna ramo",
          (deteccion.resolver_ramo(date(2026, 8, 3), cfg) or {}).get("nombre") == "R")
    check("un sabado no asigna ramo", deteccion.resolver_ramo(date(2026, 8, 8), cfg) is None)
    check("la semana de semestre se calcula bien",
          deteccion.calcular_semana_semestre(date(2026, 8, 10), "2026-08-03") == 2)


def probar_flashcards() -> None:
    print("\n== extraccion de flashcards ==")
    nota = """## 10 preguntas
(de menor a mayor dificultad, tapate las respuestas)
1. Que es la elasticidad?
2. Por que importa el excedente?

## Respuestas modelo
(las que daria alguien que domina el tema)
1. La sensibilidad de la cantidad ante el precio.
2. Porque mide el bienestar.

## Otra seccion
texto que no debe entrar
"""
    t = extraer_flashcards.extraer_preguntas_respuestas(nota)
    check("extrae exactamente dos tarjetas", len(t) == 2, str(t))
    check("no cuela la linea de instruccion como pregunta",
          all("dificultad" not in p and "domina el tema" not in r for p, r in t))
    check("empareja cada pregunta con su respuesta",
          t[0][0].startswith("Que es la elasticidad") and t[0][1].startswith("La sensibilidad"))
    check("no arrastra la seccion siguiente",
          all("no debe entrar" not in p + r for p, r in t))


def probar_docx() -> None:
    print("\n== generacion del .docx ==")
    md = """---
ramo: PRUEBA
---
# Titulo
Texto con **negrita**.

| Concepto | Definicion |
| --- | --- |
| Elasticidad | Sensibilidad |

## Preguntas de repaso
esto no debe aparecer en el docx
"""
    tmp = Path(tempfile.mkdtemp())
    try:
        ruta = docx_generator.generar_docx(
            {"numero_clase": 1, "fecha": "2026-08-05", "ramo": "PRUEBA"},
            "Clase de prueba",
            "# Fuente\nTexto de respaldo.",
            md,
            [{"concepto": "Elasticidad", "por_que": "se repite al inicio y al cierre"}],
            {"rutas": {"output": str(tmp)}},
        )
        check("crea el archivo .docx", ruta.is_file() and ruta.stat().st_size > 0)
        check("usa el nombre de clase correcto",
              ruta.name == "Clase 01 - 2026-08-05 - Clase de prueba.docx", ruta.name)

        from docx import Document
        doc = Document(str(ruta))
        texto = "\n".join(p.text for p in doc.paragraphs)
        check("renderiza las tablas markdown", len(doc.tables) >= 2, f"tablas={len(doc.tables)}")
        check("omite las secciones de repaso espaciado", "esto no debe aparecer" not in texto)
        check("quita el frontmatter YAML", "ramo: PRUEBA" not in texto)
        check("la negrita queda sin asteriscos", "**negrita**" not in texto and "negrita" in texto)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def probar_aislamiento_del_ensayo() -> None:
    """El bloque que mas importa: que un ensayo no pueda tocar nada real."""
    print("\n== aislamiento del modo ensayo ==")
    config_real = {
        "rutas": {"input": "/real/input", "output": "/real/output",
                  "procesados": "/real/procesados",
                  "vault_obsidian": "/real/vault", "transcriptotem": "/real/tt"},
        "semestre": {"fecha_inicio": "2026-08-03"},
        "ramos": {}, "carpetas_ramo": {"RAMO VIEJO": "/real/vault/RAMO VIEJO"},
    }
    pendientes_antes = sorted(p.name for p in PENDIENTES_DIR_POR_DEFECTO.glob("*")) \
        if PENDIENTES_DIR_POR_DEFECTO.exists() else []

    cfg, sandbox = ensayo.preparar(config_real)
    try:
        for clave in ("input", "output", "procesados", "vault_obsidian"):
            check(f"la ruta '{clave}' apunta al sandbox", str(sandbox) in cfg["rutas"][clave])
        check("el ensayo queda marcado", ensayo.es_ensayo(cfg))
        check("una config normal no se confunde con un ensayo", not ensayo.es_ensayo(config_real))
        check("el cache de carpetas reales se descarta", cfg["carpetas_ramo"] == {})
        check("la config original no se muta",
              config_real["rutas"]["vault_obsidian"] == "/real/vault")
        check("los intermedios se redirigen al sandbox", str(sandbox) in str(dir_pendientes()))

        carpeta, _ = carpetas.resolver_carpeta_ramo("RAMO NUEVO", cfg["rutas"]["vault_obsidian"], cfg)
        check("una carpeta de ramo nueva cae dentro del sandbox", str(sandbox) in str(carpeta))
    finally:
        usar_dir_pendientes(None)
        shutil.rmtree(sandbox, ignore_errors=True)

    check("los intermedios vuelven a la carpeta real al terminar",
          dir_pendientes() == PENDIENTES_DIR_POR_DEFECTO)
    pendientes_despues = sorted(p.name for p in PENDIENTES_DIR_POR_DEFECTO.glob("*")) \
        if PENDIENTES_DIR_POR_DEFECTO.exists() else []
    check("el ensayo no dejo archivos en la carpeta real",
          pendientes_antes == pendientes_despues)


def probar_archivado_no_destructivo() -> None:
    print("\n== el ensayo no mueve el audio original ==")
    from orquestador.archivado import archivar_audio

    tmp = Path(tempfile.mkdtemp())
    try:
        origen = tmp / "clase original.m4a"
        origen.write_bytes(b"audio")
        trabajo = {"ramo": "RAMO", "numero_clase": 1, "fecha": "2026-08-05",
                   "archivos": [str(origen)]}

        cfg_ensayo = {"rutas": {"procesados": str(tmp / "dest")}, ensayo.CLAVE: True}
        archivar_audio(trabajo, "Titulo", cfg_ensayo)
        check("en ensayo el audio original sigue en su lugar", origen.is_file())
        check("en ensayo si queda una copia archivada",
              len(list((tmp / "dest").rglob("*.m4a"))) == 1)

        cfg_real = {"rutas": {"procesados": str(tmp / "dest_real")}}
        archivar_audio(trabajo, "Titulo", cfg_real)
        check("fuera de ensayo el audio si se mueve", not origen.exists())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def probar_dialogo_nunca_descarta_solo() -> None:
    """
    Descartar una grabacion tiene que costar un clic explicito. Esto ya fallo
    una vez con una clase real: el timeout y el boton por defecto llevaban los
    dos a ignorar, y el audio se archivo solo mientras nadie miraba.
    """
    print("\n== el dialogo nunca descarta por su cuenta ==")
    from orquestador import dialogo_no_reconocido as dlg

    original = dlg._mostrar_dialogo_principal
    casos = [
        ("timeout o ventana cerrada", None, "solo_transcribir"),
        ("clic explicito en Ignorar", dlg.OPCION_IGNORAR, "ignorar"),
        ("clic en Solo transcribir", dlg.OPCION_SOLO_TRANSCRIBIR, "solo_transcribir"),
    ]
    try:
        for nombre, respuesta, esperado in casos:
            dlg._mostrar_dialogo_principal = lambda _t, _r=respuesta: _r
            accion = dlg.preguntar_que_hacer({"archivos": [], "fecha": "1970-01-20",
                                              "dia_semana": "martes"}, {})["accion"]
            check(f"{nombre} -> {esperado}", accion == esperado, f"dio '{accion}'")

        # Abandonar a mitad de elegir el ramo tampoco puede descartar.
        dlg._mostrar_dialogo_principal = lambda _t: dlg.OPCION_APLICAR_SKILLS
        original_ramo = dlg._elegir_ramo
        dlg._elegir_ramo = lambda _c: None
        try:
            accion = dlg.preguntar_que_hacer({"archivos": [], "fecha": "1970-01-20",
                                              "dia_semana": "martes"}, {})["accion"]
            check("abandonar la eleccion de ramo -> solo_transcribir",
                  accion == "solo_transcribir", f"dio '{accion}'")
        finally:
            dlg._elegir_ramo = original_ramo

    finally:
        dlg._mostrar_dialogo_principal = original

    import inspect
    fuente = inspect.getsource(original)
    check("el boton por defecto del dialogo no es el que descarta",
          "default button {_escapar(OPCION_IGNORAR)}" not in fuente
          and "OPCION_SOLO_TRANSCRIBIR" in fuente)


if __name__ == "__main__":
    probar_nombres()
    probar_deteccion()
    probar_flashcards()
    probar_docx()
    probar_aislamiento_del_ensayo()
    probar_archivado_no_destructivo()
    probar_dialogo_nunca_descarta_solo()

    print()
    if fallos:
        print(f"FALLARON {len(fallos)}: " + ", ".join(fallos))
        raise SystemExit(1)
    print("Todas las pruebas pasaron.")

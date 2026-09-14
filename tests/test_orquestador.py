"""
Pruebas del orquestador que no cuestan tokens ni tocan nada real.

Cubren la logica determinista (fechas, nombres, la hoja de repaso) y, sobre
todo, las garantias de aislamiento del modo ensayo: que un ensayo no pueda
escribir en el vault real, en config.json ni en la carpeta de intermedios.
Esa ultima garantia existe porque ya fallo una vez: un ensayo
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

from orquestador import carpetas, deteccion, ensayo, nombres
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
        original_ramo = dlg.elegir_ramo
        dlg.elegir_ramo = lambda _c: None
        try:
            accion = dlg.preguntar_que_hacer({"archivos": [], "fecha": "1970-01-20",
                                              "dia_semana": "martes"}, {})["accion"]
            check("abandonar la eleccion de ramo -> solo_transcribir",
                  accion == "solo_transcribir", f"dio '{accion}'")
        finally:
            dlg.elegir_ramo = original_ramo

    finally:
        dlg._mostrar_dialogo_principal = original

    import inspect
    fuente = inspect.getsource(original)
    check("el boton por defecto del dialogo no es el que descarta",
          "default button {_escapar(OPCION_IGNORAR)}" not in fuente
          and "OPCION_SOLO_TRANSCRIBIR" in fuente)


def probar_el_nombre_del_archivo_manda_sobre_el_dia() -> None:
    """
    El caso real que esto arregla: el 26-08-2026 (miercoles) se subieron dos
    grabaciones, la clase de BIOLOGIA CELULAR y una reunion informativa
    de un ramo anexo. Como el dia tenia ramo asignado, las dos se archivaron
    como esa clase, sin preguntar, y chocaron de numero.

    Los nombres de archivo de aqui son los reales que pasaron por el sistema,
    con las faltas de ortografia incluidas. Son la calibracion del umbral: si
    alguien lo mueve, esto tiene que seguir pasando.
    """
    print("\n== el nombre del archivo manda sobre el dia de la semana ==")
    from orquestador import ramo_por_nombre as rpn

    config = {
        "ramos": {
            "lunes": {"nombre": "HISTORIA CONTEMPORÁNEA", "perfil_whisper": "es-chile"},
            "martes": {"nombre": "SISTEMAS Y ESTRUCTURA DIGITAL", "perfil_whisper": "es-chile"},
            "miercoles": {"nombre": "BIOLOGÍA CELULAR", "perfil_whisper": "es-chile"},
            "jueves": {"nombre": "TERMODINÁMICA", "perfil_whisper": "es-chile"},
            "viernes": {"nombre": "TALLER DE ANÁLISIS NUMÉRICO III", "perfil_whisper": "es-chile"},
        },
        "semestre": {"fecha_inicio": "2026-08-03"},
    }

    reconoce = [
        ("Historia contemporánea 24.08.26.m4a", "HISTORIA CONTEMPORÁNEA"),
        ("Termodinámica 13.08.26.m4a", "TERMODINÁMICA"),
        ("Biología celular 26.08.26.m4a", "BIOLOGÍA CELULAR"),
        # Con la falta de ortografia del estudiante y sin la palabra "Taller".
        ("Analicis Numerico III 21.08.26.m4a", "TALLER DE ANÁLISIS NUMÉRICO III"),
        # "Sistema" en singular.
        ("Sistema y estructura digital 18.8.26.m4a", "SISTEMAS Y ESTRUCTURA DIGITAL"),
        # Otros formatos de fecha que el estudiante usa.
        ("Historia contemporánea 3-8-26.m4a", "HISTORIA CONTEMPORÁNEA"),
        # Sufijo de parte que agrega el propio sistema al cortar un audio largo.
        ("Historia contemporánea 10.08.26 - parte 03.m4a", "HISTORIA CONTEMPORÁNEA"),
    ]
    for nombre, esperado in reconoce:
        estado, info = rpn.resolver([nombre], config)
        check(f"'{nombre[:34]}' -> {esperado[:24]}",
              estado == rpn.RECONOCIDO and info["nombre"] == esperado,
              f"dio {estado} / {info}")

    # El caso que motivo todo: palabras reales que no son ningun ramo del
    # horario. No puede caer al dia de la semana.
    pregunta = [
        "Evaluación conocimientos intermedios 26.08.26.m4a",
        "Reunión de coordinación 30.08.m4a",
        "Conversación con el ayudante.m4a",
    ]
    for nombre in pregunta:
        estado, info = rpn.resolver([nombre], config)
        check(f"'{nombre[:34]}' -> pregunta",
              estado == rpn.NO_CALZA and info is None, f"dio {estado} / {info}")

    # Un nombre sin contenido no es evidencia de nada: ahi si manda el dia.
    for nombre in ["Nota de voz 3.m4a", "Grabación 12.m4a", "audio.m4a", "Clase.m4a"]:
        estado, _ = rpn.resolver([nombre], config)
        check(f"'{nombre}' -> sin senal, decide el dia", estado == rpn.SIN_SENAL,
              f"dio {estado}")

    # Un ramo agregado a mano tiene que reconocerse igual que los del horario.
    con_adicional = dict(config)
    con_adicional["ramos_adicionales"] = {
        "EIC - EVALUACIÓN INTERMEDIA DE CONOCIMIENTOS": {"perfil_whisper": "es-chile"}
    }
    estado, info = rpn.resolver(["Evaluación conocimientos intermedios 26.08.26.m4a"], con_adicional)
    check("una vez creado el ramo, la siguiente reunion se reconoce sola",
          estado == rpn.RECONOCIDO and info["nombre"].startswith("EIC"),
          f"dio {estado} / {info}")

    # Partes de ramos distintos agrupadas: ya fusiono dos clases una vez.
    estado, _ = rpn.resolver(
        ["Biología celular 19.08.26.m4a", "Termodinámica 20.08.26.m4a"], config)
    check("dos ramos distintos en un mismo trabajo -> pregunta", estado == rpn.NO_CALZA,
          f"dio {estado}")

    # Y el efecto completo sobre la deteccion: el mismo miercoles, dos
    # grabaciones, cada una a su lugar.
    miercoles = date(2026, 8, 26)
    clase = deteccion.resolver_ramo_de_grabacion(
        ["Biología celular 26.08.26.m4a"], miercoles, config)
    reunion = deteccion.resolver_ramo_de_grabacion(
        ["Evaluación conocimientos intermedios 26.08.26.m4a"], miercoles, config)
    check("el miercoles, la clase real sigue siendo la clase",
          clase and clase["nombre"] == "BIOLOGÍA CELULAR", f"dio {clase}")
    check("el mismo miercoles, la reunion no se archiva sola",
          reunion is None, f"dio {reunion}")

    # Sin nombre util, el comportamiento de siempre: manda el dia.
    por_dia = deteccion.resolver_ramo_de_grabacion(["Nota de voz 3.m4a"], miercoles, config)
    check("sin nombre util se mantiene el comportamiento de siempre",
          por_dia and por_dia["nombre"] == "BIOLOGÍA CELULAR", f"dio {por_dia}")


def probar_pantalla_de_confirmacion() -> None:
    """
    La pantalla pregunta por todas las grabaciones juntas antes de empezar, y
    reemplaza al dialogo de a una por vez. Lo que se prueba es que ningun
    camino de fallo deje al estudiante peor que antes de que existiera:

    - Sin el binario compilado se sigue por el dialogo viejo, que SI pregunta.
      Caer a "no hacer nada" seria dejar de preguntar algo que hoy se pregunta.
    - Con el binario presente pero fallando (no arranca, devuelve basura, vence
      el tiempo), se procesa lo reconocido y lo dudoso queda para el proximo
      clic. Es el comportamiento anterior a la pantalla.
    - Una respuesta invalida no se cree a medias: cae entera al defecto.
    """
    print("\n== la pantalla de confirmacion nunca deja al usuario peor ==")
    from orquestador import pantalla_confirmacion as pc

    config = {
        "ramos": {"miercoles": {"nombre": "BIOLOGÍA CELULAR", "perfil_whisper": "es-chile"}},
        "ramos_adicionales": {},
    }
    trabajos = [
        {"clave": "k1", "archivos": ["/x/Biología celular 26.08.26.m4a"],
         "fecha": "2026-08-26", "dia_semana": "miercoles",
         "ramo": "BIOLOGÍA CELULAR", "reconocido": True},
        {"clave": "k2", "archivos": ["/x/Evaluación conocimientos intermedios 26.08.26.m4a"],
         "fecha": "2026-08-26", "dia_semana": "miercoles", "ramo": None, "reconocido": False},
    ]

    # La duracion se mide con ffprobe sobre archivos que aqui no existen.
    original_duracion = pc.duracion_audio_segundos
    pc.duracion_audio_segundos = lambda _r: None
    original_binario = pc.BINARIO
    try:
        descripcion = pc.describir(trabajos, config)
        check("describe cada grabacion con el origen de su ramo",
              descripcion["grabaciones"][0]["origen"] == "nombre"
              and descripcion["grabaciones"][1]["origen"] is None,
              str([g["origen"] for g in descripcion["grabaciones"]]))
        check("ofrece los ramos conocidos para elegir",
              "BIOLOGÍA CELULAR" in descripcion["ramos"])

        # Sin binario: hay que seguir preguntando por el camino viejo.
        pc.BINARIO = Path("/no/existe/ConfirmarGrabaciones")
        check("sin el binario compilado se cae al dialogo de siempre",
              pc.preguntar(trabajos, config) is None)

        # Con binario, pero la ventana falla o vence el tiempo.
        pc.BINARIO = original_binario
        por_defecto = pc._decisiones_por_defecto(descripcion)
        check("por defecto, lo reconocido se procesa",
              por_defecto["k1"]["que_hacer"] == pc.PROCESAR)
        check("por defecto, lo dudoso queda para el proximo clic",
              por_defecto["k2"]["que_hacer"] == pc.OMITIR)

        # Respuestas que no se pueden creer.
        invalidas = [
            ("una clave que no existe", {"accion": "procesar", "decisiones": [
                {"clave": "inventada", "que_hacer": "procesar", "ramo": "X"}]}),
            ("una accion desconocida", {"accion": "procesar", "decisiones": [
                {"clave": "k1", "que_hacer": "borrar_todo"}]}),
            ("procesar sin ramo", {"accion": "procesar", "decisiones": [
                {"clave": "k1", "que_hacer": "procesar", "ramo": "  "}]}),
            ("la ventana se cerro", {"accion": "cerrada"}),
            ("vencio el tiempo", {"accion": "timeout"}),
        ]
        for nombre, respuesta in invalidas:
            check(f"{nombre} -> se ignora entera",
                  pc._validar(respuesta, descripcion) is None)

        # Una respuesta valida si se respeta.
        buena = {"accion": "procesar", "decisiones": [
            {"clave": "k1", "que_hacer": "procesar", "ramo": "BIOLOGÍA CELULAR"},
            {"clave": "k2", "que_hacer": "procesar", "ramo": "EIC", "ramo_nuevo": True},
        ]}
        validadas = pc._validar(buena, descripcion)
        check("una respuesta valida se respeta", validadas is not None
              and validadas["k2"]["ramo"] == "EIC" and validadas["k2"]["ramo_nuevo"])

        # Una grabacion sobre la que la ventana no dijo nada conserva su default.
        parcial = {"accion": "procesar", "decisiones": [
            {"clave": "k1", "que_hacer": "omitir"}]}
        validadas = pc._validar(parcial, descripcion)
        check("lo que la ventana no menciona conserva su valor por defecto",
              validadas["k2"]["que_hacer"] == pc.OMITIR, str(validadas))
    finally:
        pc.duracion_audio_segundos = original_duracion
        pc.BINARIO = original_binario


def probar_decisiones_de_pantalla_se_aplican() -> None:
    """
    Que lo elegido en la pantalla llegue intacto al trabajo, sin transcribir
    nada ni abrir ventanas. Cubre en particular la numeracion: un ramo elegido
    a mano no puede numerarse por semana de semestre, que ya dio "Clase -2949"
    en vivo cuando la fecha caia fuera del calendario.
    """
    print("\n== lo elegido en la pantalla se aplica al trabajo ==")
    from orquestador import transcripcion

    with tempfile.TemporaryDirectory() as tmp:
        config = {
            "rutas": {"procesados": tmp},
            "ramos": {"miercoles": {"nombre": "BIOLOGÍA CELULAR", "perfil_whisper": "es-chile"}},
            "ramos_adicionales": {},
        }
        guardados = []
        original_guardar = transcripcion.guardar_config
        transcripcion.guardar_config = lambda c: guardados.append(c)
        try:
            # Omitir no toca nada.
            t = {"clave": "k", "fecha": "2026-08-26", "reconocido": False, "ramo": None}
            r = transcripcion._aplicar_decision_de_pantalla(t, {"que_hacer": "omitir"}, config)
            check("omitir -> el trabajo no sigue", r == "omitir")

            # Solo transcribir deja el texto sin archivar bajo ningun ramo.
            t = {"clave": "k", "fecha": "2026-08-26", "reconocido": True,
                 "ramo": "BIOLOGÍA CELULAR"}
            r = transcripcion._aplicar_decision_de_pantalla(
                t, {"que_hacer": "solo_transcribir"}, config)
            check("solo transcribir -> sigue pero sin ramo",
                  r == "seguir" and not t["reconocido"] and t["ramo"] is None)

            # Un ramo nuevo se guarda para que la proxima vez se reconozca solo.
            t = {"clave": "k", "fecha": "2026-08-26", "reconocido": False, "ramo": None}
            r = transcripcion._aplicar_decision_de_pantalla(
                t, {"que_hacer": "procesar", "ramo": "EIC", "ramo_nuevo": True}, config)
            check("un ramo nuevo queda guardado en config",
                  "EIC" in config.get("ramos_adicionales", {}) and guardados)
            check("y el trabajo queda con ese ramo",
                  t["reconocido"] and t["ramo"] == "EIC")
            check("numerado por orden cronologico, no por semana de semestre",
                  t["numeracion"] == "orden" and t["numero_clase"] == 1,
                  f"dio {t.get('numeracion')} / {t.get('numero_clase')}")

            # Confirmar lo que ya estaba detectado no renumera.
            t = {"clave": "k", "fecha": "2026-08-26", "reconocido": True,
                 "ramo": "BIOLOGÍA CELULAR", "numero_clase": 4,
                 "numeracion": "calendario"}
            transcripcion._aplicar_decision_de_pantalla(
                t, {"que_hacer": "procesar", "ramo": "BIOLOGÍA CELULAR"}, config)
            check("confirmar lo detectado conserva la numeracion por calendario",
                  t["numero_clase"] == 4 and t["numeracion"] == "calendario",
                  f"dio {t.get('numeracion')} / {t.get('numero_clase')}")
        finally:
            transcripcion.guardar_config = original_guardar


def probar_bitacora_deshace_todo() -> None:
    """
    El aborto promete dejar el disco como estaba. Si el deshacer falla, esa
    promesa se rompe justo cuando el estudiante ya decidio cancelar, o sea en
    el peor momento para descubrirlo.
    """
    print("\n== abortar deja todo como estaba ==")
    from orquestador.bitacora import Bitacora

    base = Path(tempfile.mkdtemp())
    try:
        # Estado inicial: una carpeta de ramo con una nota que ya existia.
        vault = base / "vault" / "RAMO"
        vault.mkdir(parents=True)
        indice = vault / "indice.md"
        indice.write_text("contenido original", encoding="utf-8")

        entrada = base / "Input"
        entrada.mkdir()
        audio = entrada / "clase.m4a"
        audio.write_bytes(b"audio")

        b = Bitacora(base / "bitacora.json")

        # Lo que hace una corrida.
        b.fotografiar_carpeta(vault)
        (vault / "Fuente - nueva.md").write_text("nota nueva", encoding="utf-8")
        (vault / "Aprendizaje - nueva.md").write_text("otra nota", encoding="utf-8")
        indice.write_text("contenido MODIFICADO por la skill", encoding="utf-8")

        carpeta_nueva = base / "vault" / "RAMO RECIEN CREADO"
        carpeta_nueva.mkdir()
        b.carpeta_creada(carpeta_nueva)

        hoja = base / "salida.html"
        hoja.write_bytes(b"<html></html>")
        b.archivo_creado(hoja)

        destino = base / "Procesados" / "clase archivada.m4a"
        destino.parent.mkdir(parents=True)
        b.audio_movido(audio, destino)
        shutil.move(str(audio), str(destino))

        check("durante la corrida el audio ya no esta en Input", not audio.exists())

        # Abortar.
        revertido = b.deshacer()

        check("las notas nuevas se borraron",
              not (vault / "Fuente - nueva.md").exists()
              and not (vault / "Aprendizaje - nueva.md").exists())
        check("la nota que ya existia sigue ahi", indice.is_file())
        check("y con su contenido original",
              indice.read_text(encoding="utf-8") == "contenido original",
              indice.read_text(encoding="utf-8"))
        check("la carpeta creada se elimino", not carpeta_nueva.exists())
        check("la hoja se borro", not hoja.exists())
        check("el audio volvio a Input", audio.is_file() and not destino.exists())
        check("el audio conserva su contenido", audio.read_bytes() == b"audio")
        check("se informa lo que se revirtio", len(revertido) >= 4, str(revertido))
        check("la bitacora se limpia al terminar", not (base / "bitacora.json").exists())
    finally:
        shutil.rmtree(base, ignore_errors=True)


def probar_bitacora_no_borra_lo_ajeno() -> None:
    print("\n== abortar no toca lo que no puso el sistema ==")
    from orquestador.bitacora import Bitacora

    base = Path(tempfile.mkdtemp())
    try:
        carpeta = base / "RAMO"
        carpeta.mkdir()
        b = Bitacora(base / "b.json")
        b.carpeta_creada(carpeta)
        ajeno = carpeta / "algo mio.md"
        ajeno.write_text("no es del sistema", encoding="utf-8")

        b.deshacer()
        check("una carpeta con algo dentro no se borra", carpeta.is_dir())
        check("el archivo ajeno sigue intacto", ajeno.is_file())
    finally:
        shutil.rmtree(base, ignore_errors=True)


def probar_seccion_critica() -> None:
    """Durante el movimiento del audio el aborto se encola, no se ignora."""
    print("\n== el tramo delicado no se puede cortar por la mitad ==")
    from orquestador import cancelacion

    llego_al_final = False
    try:
        with cancelacion.seccion_critica():
            check("mientras dura, el estado dice que no se puede interrumpir",
                  cancelacion._seccion_critica.locked())
            # Simula el pedido de aborto llegando justo aqui.
            cancelacion._al_recibir_senal(15, None)
            llego_al_final = True
    except cancelacion.Abortado:
        check("el aborto pedido adentro se aplica al salir, no se pierde", True)
    else:
        check("el aborto pedido adentro se aplica al salir, no se pierde", False)

    check("el tramo se completo antes de abortar", llego_al_final)
    check("el candado queda libre despues", not cancelacion._seccion_critica.locked())


def probar_audio_largo_se_corta_solo() -> None:
    """
    Una clase real de 1 h 56 min hizo que Whisper devolviera cero caracteres sin
    lanzar ningun error, y el pipeline siguio hasta entregarle un archivo vacio
    al modelo. Ahora los audios largos se cortan antes de transcribir, y una
    transcripcion vacia detiene la corrida en vez de gastar una llamada.
    """
    print("\n== audios largos y transcripciones vacias ==")
    import subprocess as sp

    from orquestador import transcripcion as tr
    from orquestador.estado_vivo import duracion_audio_segundos

    check("el umbral deja pasar una clase corta sin cortarla",
          tr.UMBRAL_PARTIR_SEGUNDOS > 30 * 60)
    check("el trozo no supera lo ya probado", tr.DURACION_TROZO_SEGUNDOS <= 20 * 60)

    tmp = Path(tempfile.mkdtemp())
    try:
        audio = tmp / "largo.m4a"
        sp.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                "-i", "sine=frequency=440:duration=50",
                "-c:a", "aac", str(audio), "-y"], check=True, capture_output=True)

        original = tr.DURACION_TROZO_SEGUNDOS
        tr.DURACION_TROZO_SEGUNDOS = 20
        try:
            trozos = tr._partir_audio(str(audio), tmp / "trozos")
            check("un audio largo se parte en varios trozos", len(trozos) == 3, str(len(trozos)))
            check("los trozos quedan en orden",
                  [x.name for x in trozos] == sorted(x.name for x in trozos))
            total = sum(duracion_audio_segundos(x) or 0 for x in trozos)
            check("no se pierde audio al cortar", abs(total - 50) < 2, f"{total:.1f}s de 50s")
        finally:
            tr.DURACION_TROZO_SEGUNDOS = original

        try:
            tr._verificar_parte("", str(audio), 900)
            check("una transcripcion vacia detiene la corrida", False)
        except ValueError as e:
            check("una transcripcion vacia detiene la corrida", True)
            check("el mensaje avisa que el audio no se perdio", "sigue donde estaba" in str(e))
            check("y sugiere cortarlo en partes", "partes" in str(e))

        try:
            tr._verificar_parte("palabra " * 300, str(audio), 900)
            check("una transcripcion normal pasa sin molestar", True)
        except ValueError:
            check("una transcripcion normal pasa sin molestar", False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def probar_el_borrado_no_alcanza_tus_carpetas() -> None:
    """
    Cortar el audio en trozos implica borrarlos despues, y ese es el unico
    borrado que el sistema hace solo. Se prueba que NO PUEDA tocar otra cosa,
    no que "normalmente no la toque": perder grabaciones o notas de clase no
    tiene vuelta atras.
    """
    print("\n== el borrado de trozos no puede alcanzar nada mas ==")
    import tempfile as tf

    from orquestador import transcripcion as tr

    # 1. Solo borra carpetas creadas por el sistema, dentro del area temporal.
    propia = Path(tf.mkdtemp(prefix=tr.PREFIJO_TROZOS))
    (propia / "trozo.m4a").write_bytes(b"x")
    tr._borrar_carpeta_de_trozos(propia)
    check("borra su propia carpeta temporal", not propia.exists())

    # 2. Una carpeta temporal ajena (otro prefijo) no se toca.
    ajena = Path(tf.mkdtemp(prefix="algo_del_usuario_"))
    try:
        (ajena / "importante.md").write_text("no borrar", encoding="utf-8")
        tr._borrar_carpeta_de_trozos(ajena)
        check("no toca una carpeta temporal con otro nombre", ajena.exists())
    finally:
        shutil.rmtree(ajena, ignore_errors=True)

    # 3. Aunque el nombre calce, fuera del area temporal no se borra.
    fuera = Path(tf.mkdtemp()) / f"{tr.PREFIJO_TROZOS}falsa"
    fuera.mkdir(parents=True)
    simulada = fuera.parent / "Procesados"
    simulada.mkdir()
    (simulada / "clase.m4a").write_bytes(b"grabacion real")
    try:
        for objetivo in (Path.home() / "Documents", simulada, Path("/")):
            tr._borrar_carpeta_de_trozos(objetivo)
        check("no borra Documents, ni Procesados, ni la raiz",
              (Path.home() / "Documents").exists() and (simulada / "clase.m4a").exists())
    finally:
        shutil.rmtree(fuera.parent, ignore_errors=True)

    # 4. La ruta del audio original nunca entra en la carpeta de trozos.
    import inspect
    fuente = inspect.getsource(tr._transcribir_archivo)
    check("los trozos se crean en una carpeta temporal recien hecha",
          "tempfile.mkdtemp(prefix=PREFIJO_TROZOS)" in fuente)
    # Se mira el codigo, no la documentacion: el docstring justamente explica
    # que no se usa glob, y buscar la palabra ahi daba un falso positivo.
    cuerpo = inspect.getsource(tr._borrar_carpeta_de_trozos)
    cuerpo = cuerpo.split('"""')[-1]
    check("no se borra por patron ni comodin",
          "glob" not in cuerpo and "*" not in cuerpo, cuerpo.strip()[:60])
    check("se comprueba el area temporal antes de borrar",
          "gettempdir" in cuerpo and "is_relative_to" in cuerpo)


def probar_dos_clases_no_se_fusionan() -> None:
    """
    Dos clases reales terminaron en un mismo documento: "Biologia
    celular 19.08.26" y "Termodinamica 20.08.26" se copiaron a Input la
    misma noche, las dos quedaron con mtime del 20, se agruparon como una sola
    clase de dos partes y mezclaron dos ramos distintos. El nombre tenia la
    fecha correcta y se estaba ignorando.
    """
    print("\n== dos clases distintas no se fusionan ==")
    import os
    from datetime import timedelta

    hoy = date.today()
    ayer = hoy - timedelta(days=1)

    tmp = Path(tempfile.mkdtemp())
    try:
        def crear(nombre: str, mtime_dia: date) -> Path:
            f = tmp / nombre
            f.write_bytes(b"audio")
            ts = __import__("time").mktime(mtime_dia.timetuple())
            os.utime(f, (ts, ts))
            return f

        # El caso real: dos clases de dias distintos, copiadas el mismo dia.
        a = crear(f"Biología celular {ayer:%d.%m.%y}.m4a", hoy)
        b = crear(f"Termodinámica {hoy:%d.%m.%y}.m4a", hoy)

        check("la fecha del nombre gana sobre la del archivo",
              deteccion._resolver_fecha_archivo(a) == ayer,
              str(deteccion._resolver_fecha_archivo(a)))
        grupos = deteccion.agrupar_por_fecha([a, b])
        check("quedan como dos clases separadas", len(grupos) == 2, str(list(grupos)))
        check("ninguna queda con dos audios",
              all(len(v) == 1 for v in grupos.values()))

        # Sin fecha en el nombre se sigue usando la del archivo.
        c = crear("grabacion sin fecha.m4a", ayer)
        check("sin fecha en el nombre manda el archivo",
              deteccion._resolver_fecha_archivo(c) == ayer)

        # Una fecha del futuro en el nombre no se cree.
        futuro = hoy + timedelta(days=30)
        d = crear(f"clase {futuro:%d.%m.%y}.m4a", hoy)
        check("una fecha futura en el nombre se descarta",
              deteccion._resolver_fecha_archivo(d) == hoy)

        # Un numero que parece fecha pero es de hace decadas tampoco.
        e = crear("Capitulo 1.2.99 repaso.m4a", ayer)
        check("un numero viejo que parece fecha se descarta",
              deteccion._resolver_fecha_archivo(e) == ayer)

        # Una clase partida de verdad por el estudiante si debe agruparse.
        f1 = crear(f"Historia {ayer:%d.%m.%y} parte A.m4a", hoy)
        f2 = crear(f"Historia {ayer:%d.%m.%y} parte B.m4a", hoy)
        g = deteccion.agrupar_por_fecha([f1, f2])
        check("dos archivos de la MISMA fecha si se agrupan juntos",
              len(g) == 1 and len(list(g.values())[0]) == 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def probar_las_notificaciones_no_se_pierden() -> None:
    """
    Una actualizacion de Homebrew dejo terminal-notifier sin poder entregar
    avisos, y el codigo no miraba el resultado: el estudiante habria dejado de
    recibir notificaciones sin enterarse. Ahora un fallo cae a la via nativa.
    """
    print("\n== las notificaciones no se pierden en silencio ==")
    from orquestador import notificaciones as n

    original_tn, original_as = n._con_terminal_notifier, n._con_applescript
    try:
        # Cuando la via preferida funciona, no se usa el respaldo.
        usados = []
        n._con_terminal_notifier = lambda *a, **k: usados.append("tn") or True
        n._con_applescript = lambda *a, **k: usados.append("as")
        n._notificar("t", "s", "m")
        check("si terminal-notifier entrega, no se duplica el aviso", usados == ["tn"], str(usados))

        # Cuando falla, el aviso igual llega.
        usados.clear()
        n._con_terminal_notifier = lambda *a, **k: usados.append("tn") or False
        n._notificar("t", "s", "m")
        check("si terminal-notifier falla, se usa la via nativa",
              usados == ["tn", "as"], str(usados))

        # Y si las dos fallan, no revienta el procesamiento.
        def explota(*a, **k):
            raise RuntimeError("sin notificaciones")
        n._con_terminal_notifier = lambda *a, **k: False
        n._con_applescript = explota
        try:
            n._notificar("t", "s", "m")
            check("un aviso que no se puede entregar no tumba la clase", True)
        except Exception as e:
            check("un aviso que no se puede entregar no tumba la clase", False,
                  f"propago {type(e).__name__}")
    finally:
        n._con_terminal_notifier, n._con_applescript = original_tn, original_as

    # Pase lo que pase, queda registrado en Estado.txt.
    import inspect
    check("todo aviso queda anotado antes de intentar entregarlo",
          "_anotar_estado" in inspect.getsource(n._notificar))
    check("el texto se escapa antes de pasarlo a AppleScript",
          "_escapar_applescript" in inspect.getsource(n._con_applescript))


def probar_error_de_sesion_se_explica() -> None:
    """
    La sesion de Claude Code caduco y el estudiante leyo "La skill termino con
    error: success", que no dice nada. La explicacion venia en el campo
    `result` del SDK y no se estaba mirando, asi que no habia forma de saber
    que lo que tocaba era volver a iniciar sesion.
    """
    print("\n== un error del modelo dice que paso de verdad ==")
    from orquestador.skill_runner import _es_sesion_caducada, describir_error_sdk

    class Falso:
        subtype = "success"
        is_error = True
        result = "Failed to authenticate: OAuth session expired and could not be refreshed"
        api_error_status = None
        terminal_reason = None
        errors = None

    texto = describir_error_sdk(Falso())
    check("el mensaje incluye la causa real", "OAuth session expired" in texto)
    check("y dice que hay que iniciar sesion de nuevo", "iniciar sesion" in texto.lower())
    check("y nombra el comando exacto", "node_modules/.bin/claude" in texto)
    check("y avisa que la transcripcion no se perdio", "transcripcion" in texto.lower())
    check("el subtype enganoso ya no va solo", texto.strip() != "subtype=success")

    check("reconoce una sesion caducada", _es_sesion_caducada(Falso.result))
    check("no confunde otro error con sesion caducada",
          not _es_sesion_caducada("API Error: 429 rate limit exceeded"))

    # Un error distinto se sigue describiendo, sin inventar el diagnostico.
    class Otro(Falso):
        result = "API Error: 529 overloaded"
    texto_otro = describir_error_sdk(Otro())
    check("otro error se muestra tal cual", "529" in texto_otro)
    check("y no sugiere iniciar sesion sin motivo",
          "node_modules/.bin/claude" not in texto_otro)


def probar_titulo_nunca_falta() -> None:
    """
    El titulo era el unico campo que finalizar_clase leia sin respaldo, y una
    linea RESULTADO_ORQUESTADOR sin el costaba la clase entera con las notas ya
    escritas. Peor: el _skill.json quedaba guardado, asi que el reintento
    fallaba en el mismo punto para siempre.
    """
    print("\n== el titulo que falta no puede costar la clase ==")
    from orquestador.skill_runner import normalizar_resultado

    r = normalizar_resultado({"fuente": "a.md"}, "TERMODINAMICA")
    check("sin titulo, usa el ramo", r["titulo"] == "TERMODINAMICA")
    check("sin conceptos, deja la lista vacia", r["conceptos_repetidos"] == [])

    check("un titulo en blanco cuenta como ausente",
          normalizar_resultado({"titulo": "   "}, "R")["titulo"] == "R")
    check("un titulo que no es texto cuenta como ausente",
          normalizar_resultado({"titulo": 5}, "R")["titulo"] == "R")
    check("un titulo bueno no se toca",
          normalizar_resultado({"titulo": "Oferta y demanda"}, "R")["titulo"]
          == "Oferta y demanda")

    check("conceptos mal formados pasan a lista vacia",
          normalizar_resultado({"titulo": "T", "conceptos_repetidos": "no es lista"},
                               "R")["conceptos_repetidos"] == [])
    check("conceptos buenos no se tocan",
          normalizar_resultado({"titulo": "T", "conceptos_repetidos": ["a", "b"]},
                               "R")["conceptos_repetidos"] == ["a", "b"])

    # Un respaldo vacio dejaria el archivo terminado en " - ".
    sin_ramo = normalizar_resultado({}, "  ")["titulo"]
    check("sin ramo tampoco queda en blanco", sin_ramo.strip() != "")
    nombre = nombres.nombre_base(1, "2026-08-13", sin_ramo)
    check("el nombre de archivo no queda colgando de un guion",
          not nombre.rstrip().endswith("-"), nombre)


def probar_error_del_sdk_se_explica() -> None:
    """
    Un fallo HTTP de la API llega con subtype "success", asi que el mensaje que
    veia el estudiante era "La skill termino con error: success". Paso en vivo y
    costo reprocesar una clase entera.
    """
    print("\n== un error del SDK tiene que decir que paso ==")
    from orquestador.skill_runner import describir_error_sdk

    class _Falso:
        def __init__(self, **kw):
            self.subtype = "success"
            self.api_error_status = None
            self.terminal_reason = None
            self.errors = None
            self.__dict__.update(kw)

    texto = describir_error_sdk(_Falso(api_error_status=529))
    check("nombra el codigo HTTP cuando lo hay", "529" in texto, texto)
    check("y no se queda solo en el subtype engañoso", texto != "subtype=success", texto)

    texto = describir_error_sdk(_Falso(terminal_reason="max_turns"))
    check("dice por que termino la corrida", "max_turns" in texto, texto)

    texto = describir_error_sdk(_Falso(errors=["se cayo la conexion"]))
    check("incluye los errores que traiga", "se cayo la conexion" in texto, texto)

    # Un ResultMessage viejo puede no traer los campos nuevos del SDK.
    class _Viejo:
        subtype = "error_during_execution"

    check("no revienta si el SDK no trae los campos nuevos",
          "error_during_execution" in describir_error_sdk(_Viejo()))


def _falsear_query(mensajes):
    """Sustituto de claude_agent_sdk.query: emite mensajes ya preparados."""
    async def _query(*a, **kw):
        for m in mensajes:
            yield m
    return _query


def _mensajes_sdk(texto: str, is_error: bool, **extra):
    """Lo que emitiria el SDK en una corrida: la respuesta y el resultado."""
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

    return [
        AssistantMessage(content=[TextBlock(text=texto)], model="falso"),
        ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=is_error,
            num_turns=3,
            session_id="sesion-1",
            usage={},
            total_cost_usd=0.0,
            **extra,
        ),
    ]


def probar_error_tardio_no_tira_el_trabajo() -> None:
    """
    Un 429 o un 529 al final de una corrida ya terminada no puede costar la
    clase. Paso en vivo dos veces: en una clase real (13 turnos perdidos y
    reprocesada entera) y en el ensayo, con las tres notas ya escritas.
    """
    print("\n== un error de la API al final no puede tirar el trabajo hecho ==")
    import asyncio

    from orquestador import skill_runner

    LINEA = ('RESULTADO_ORQUESTADOR: {"titulo": "Tema real", "fuente": "f.md", '
             '"aprendizaje": "a.md", "conceptos_repetidos": ["x"]}')

    avisos = []
    originales = (skill_runner.query, skill_runner.registrar_uso,
                  skill_runner.notificar_aviso)
    tmp = Path(tempfile.mkdtemp(prefix="pendientes_falsos_"))
    usar_dir_pendientes(tmp)
    skill_runner.registrar_uso = lambda *a, **kw: None
    skill_runner.notificar_aviso = lambda t, c: avisos.append((t, c))
    try:
        # 1. La skill alcanzo a reportar su trabajo y despues fallo la API.
        skill_runner.query = _falsear_query(
            _mensajes_sdk(LINEA, True, api_error_status=529)
        )
        r = asyncio.run(skill_runner.aplicar_skill(
            "t.txt", "TERMODINAMICA", "/tmp/vault", "slug1", "/tmp/vault/E"))
        check("la clase se salva pese al error de la API", r["titulo"] == "Tema real")
        check("el _skill.json queda guardado", (tmp / "slug1_skill.json").is_file())
        check("te avisa de que la API fallo", len(avisos) == 1, str(avisos))
        check("el aviso nombra el codigo HTTP", "529" in avisos[0][1], str(avisos))
        # Sin la terminal abierta, "2026-08-13_3e73c56e" no le dice nada a nadie.
        check("y nombra el ramo, no el slug interno",
              "TERMODINAMICA" in avisos[0][1] and "slug1" not in avisos[0][1], str(avisos))

        # 2. Sin error de la API no hay aviso que moleste.
        avisos.clear()
        skill_runner.query = _falsear_query(_mensajes_sdk(LINEA, False))
        asyncio.run(skill_runner.aplicar_skill(
            "t.txt", "TERMODINAMICA", "/tmp/vault", "slug2", "/tmp/vault/E"))
        check("una corrida limpia no dispara ningun aviso", avisos == [], str(avisos))

        # 3. Si ademas no hay nada aprovechable, revienta, pero explicando.
        skill_runner.query = _falsear_query(
            _mensajes_sdk("no reporte nada", True, api_error_status=429)
        )
        try:
            asyncio.run(skill_runner.aplicar_skill(
                "t.txt", "TERMODINAMICA", "/tmp/vault", "slug3", "/tmp/vault/E"))
            check("sin resultado utilizable si falla", False, "no revento")
        except ValueError as e:
            check("sin resultado utilizable si falla", True)
            check("y el error dice el codigo HTTP, no 'success'", "429" in str(e), str(e))

        # 4. La correccion tambien conserva su trabajo si la API falla al final.
        avisos.clear()
        corregida = ('RESULTADO_ORQUESTADOR: {"titulo": "Tema corregido", '
                     '"fuente": "f.md", "conceptos_repetidos": ["x"]}')
        skill_runner.query = _falsear_query(
            _mensajes_sdk(corregida, True, api_error_status=529)
        )
        previo = {"titulo": "Tema real", "session_id": "sesion-1"}
        r = asyncio.run(skill_runner.corregir_con_revision(
            previo, [{"que": "algo"}], "/tmp/vault", "slug4"))
        check("la correccion no se pierde por un error tardio",
              r["titulo"] == "Tema corregido", str(r))
        check("y queda marcada como corregida",
              r.get("corregido_tras_revision") is True, str(r))

        # 5. Si la correccion no reporta nada, se vuelve a lo anterior y avisa.
        avisos.clear()
        skill_runner.query = _falsear_query(
            _mensajes_sdk("no reporte nada", True, api_error_status=529)
        )
        r = asyncio.run(skill_runner.corregir_con_revision(
            previo, [{"que": "algo"}], "/tmp/vault", "slug5"))
        check("sin correccion confirmada se conserva lo anterior",
              r["titulo"] == "Tema real", str(r))
        check("y te avisa de que el documento va sin corregir",
              len(avisos) == 1 and "529" in avisos[0][1], str(avisos))
        check("ese aviso tambien nombra la clase, no el slug",
              "Tema real" in avisos[0][1] and "slug5" not in avisos[0][1], str(avisos))
    finally:
        (skill_runner.query, skill_runner.registrar_uso,
         skill_runner.notificar_aviso) = originales
        usar_dir_pendientes(None)
        shutil.rmtree(tmp, ignore_errors=True)


def probar_revision_fallida_no_dice_aprobado() -> None:
    """
    El revisor es la unica barrera antes de que el material entre al vault. Una
    revision que no llego a correr quedaba guardada como "aprobado", o sea con
    cara de comprobada y limpia, y el campo que guardaba la verdad no lo leia
    nadie.
    """
    print("\n== una revision que no corrio no puede decir 'aprobado' ==")
    import asyncio

    from orquestador import revisor as rv

    originales = (rv.query, rv.registrar_uso)
    tmp = Path(tempfile.mkdtemp(prefix="revision_falsa_"))
    usar_dir_pendientes(tmp)
    rv.registrar_uso = lambda *a, **kw: None
    try:
        previo = {"fuente": "f.md", "aprendizaje": "a.md"}

        # El revisor no alcanzo a emitir su linea.
        rv.query = _falsear_query(_mensajes_sdk("no alcance", True, api_error_status=529))
        r = asyncio.run(rv.revisar("t.txt", previo, "TERMODINAMICA", "/tmp/v", "s1"))
        check("el veredicto no es 'aprobado'", r["veredicto"] != "aprobado", str(r))
        check("dice explicitamente que no se reviso",
              r["veredicto"] == "no_revisado", str(r))
        check("y guarda el motivo con el codigo HTTP",
              "529" in r["revision_fallida"], str(r))
        # finalizar_clase decide corregir comparando contra "corregir": un
        # veredicto nuevo no puede disparar una correccion por accidente.
        check("no dispara correccion", r["veredicto"] != "corregir")
        check("y no aporta hallazgos falsos", r["hallazgos"] == [])

        # Una revision que si corrio sigue funcionando igual que siempre.
        buena = ('RESULTADO_REVISION: {"veredicto": "aprobado", "hallazgos": []}')
        rv.query = _falsear_query(_mensajes_sdk(buena, False))
        r = asyncio.run(rv.revisar("t.txt", previo, "TERMODINAMICA", "/tmp/v", "s2"))
        check("una revision real si puede aprobar", r["veredicto"] == "aprobado", str(r))
        check("y no queda marcada como fallida",
              not r.get("revision_fallida"), str(r))
    finally:
        (rv.query, rv.registrar_uso) = originales
        usar_dir_pendientes(None)
        shutil.rmtree(tmp, ignore_errors=True)


def probar_una_sola_comprobacion_de_vault() -> None:
    """
    La comprobacion que impide que una ruta colada en la transcripcion meta
    cualquier archivo del disco en la hoja estuvo duplicada en dos modulos
    (finalizar_clase y el antiguo regenerar.py, retirado el 14-09-2026). Queda
    una sola implementacion, y hoja_html la importa en vez de copiarla.
    """
    print("\n== la frontera del vault se comprueba en un solo lugar ==")
    import inspect

    from orquestador import finalizar_clase as fc
    from orquestador import hoja_html

    vault = Path(tempfile.mkdtemp(prefix="notas_falsas_"))
    try:
        (vault / "buena.md").write_text("contenido de la nota", encoding="utf-8")
        fuera = Path(tempfile.mkdtemp(prefix="fuera_")) / "secreto.md"
        fuera.parent.mkdir(parents=True, exist_ok=True)
        fuera.write_text("esto no puede terminar en la hoja", encoding="utf-8")

        leer = fc._leer_nota
        check("lee una nota de dentro del vault",
              leer(str(vault / "buena.md"), str(vault)) == "contenido de la nota")
        check("no lee nada de fuera del vault", leer(str(fuera), str(vault)) == "")
        check("una ruta vacia no revienta", leer(None, str(vault)) == "")
        check("un archivo que no existe da vacio",
              leer(str(vault / "no_existe.md"), str(vault)) == "")
        fuente_hoja = inspect.getsource(hoja_html)
        check("hoja_html usa esa misma comprobacion y no una copia",
              "def _leer_nota" not in fuente_hoja
              and "from .finalizar_clase import _leer_nota" in fuente_hoja)

        shutil.rmtree(fuera.parent, ignore_errors=True)
    finally:
        shutil.rmtree(vault, ignore_errors=True)


def _gate_deja_pasar(gate, ruta, clave: str = "file_path") -> bool:
    """Corre el hook y dice si autorizo la ruta. Devolver {} es autorizar."""
    import asyncio

    respuesta = asyncio.run(gate({"tool_input": {clave: str(ruta)}}, "id-1", None))
    return respuesta == {}


def _gate_motivo(gate, ruta) -> str:
    import asyncio

    respuesta = asyncio.run(gate({"tool_input": {"file_path": str(ruta)}}, "id-1", None))
    return respuesta["hookSpecificOutput"]["permissionDecisionReason"]


def probar_gate_de_rutas() -> None:
    """
    El gate es el unico freno real de la corrida automatizada: corre con
    permission_mode "bypassPermissions", asi que sin el Write podria escribir en
    cualquier parte del disco. Nunca habia tenido pruebas.
    """
    print("\n== el gate de rutas de la corrida automatizada ==")
    from orquestador.skill_runner import construir_gate_de_rutas

    # El prefijo evita a proposito la palabra "vault": el mensaje de denegacion
    # repite la ruta denegada, y con ella dentro no se podria comprobar que el
    # mensaje no nombre un vault entre las carpetas que si autorizo.
    vault = Path(tempfile.mkdtemp(prefix="notas_falsas_"))
    try:
        gate = construir_gate_de_rutas(RAIZ, vault)

        check("deja leer la transcripcion, que vive en el proyecto",
              _gate_deja_pasar(gate, RAIZ / "orquestador" / "transcripciones_pendientes" / "x.txt"))
        check("deja escribir la nota, que va en el vault",
              _gate_deja_pasar(gate, vault / "TERMODINAMICA" / "Clase.md"))
        check("deniega cualquier otra parte del disco",
              not _gate_deja_pasar(gate, "/etc/passwd"))
        check("deniega una carpeta vecina del proyecto",
              not _gate_deja_pasar(gate, RAIZ.parent / "Otra cosa" / "a.md"))
        check("deniega el home entero",
              not _gate_deja_pasar(gate, "~/nota.md"))

        # Glob y Grep no usan "file_path" sino "path": si el gate mirara solo
        # una de las dos claves, la otra pasaria sin control.
        check("tambien gatea la clave 'path' de Glob y Grep",
              not _gate_deja_pasar(gate, "/etc", clave="path"))

        # Una ruta con .. se resuelve antes de comparar, si no el gate se
        # esquivaria escribiendo hacia arriba desde una carpeta autorizada.
        check("un .. no escapa de una raiz autorizada",
              not _gate_deja_pasar(gate, RAIZ / ".." / ".." / "etc" / "passwd"))

        # Sin ruta no hay nada que validar (ej. una herramienta sin archivo).
        import asyncio
        check("una llamada sin ruta no se bloquea",
              asyncio.run(gate({"tool_input": {}}, "id-1", None)) == {})

        # Una etapa que solo necesita el proyecto puede correr con una sola raiz.
        # Hoy ninguna lo hace (la unica era la extraccion de llamados del antiguo
        # regenerar.py, retirado el 14-09-2026), pero el gate lo sigue aceptando
        # y el mensaje de denegacion no puede nombrar un vault que no autorizo.
        solo_proyecto = construir_gate_de_rutas(RAIZ)
        check("con una sola raiz, el vault queda fuera",
              not _gate_deja_pasar(solo_proyecto, vault / "nota.md"))
        motivo = _gate_motivo(solo_proyecto, vault / "nota.md")
        check("y el mensaje no inventa un vault que no autorizo",
              "vault" not in motivo.lower(), motivo)
        check("el mensaje dice cual es la raiz permitida", str(RAIZ) in motivo, motivo)

        # Los intermedios del ensayo viven en el temp del sistema, fuera de las
        # raices. Hoy no los lee el modelo (la metadata trae la ruta real del
        # proyecto, ver finalizar_clase), pero si algun dia se movieran ahi,
        # esta prueba lo dice en vez de fallar en vivo a mitad de una clase.
        sandbox = Path(tempfile.mkdtemp(prefix="ensayo_falso_"))
        try:
            gate_ensayo = construir_gate_de_rutas(RAIZ, sandbox / "vault")
            check("un intermedio del sandbox de ensayo no esta autorizado",
                  not _gate_deja_pasar(gate_ensayo, sandbox / "pendientes" / "x.txt"))
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)

        # Un gate sin raices denegaria todo y la corrida fallaria en el primer
        # Read, lejos de la llamada que se equivoco.
        try:
            construir_gate_de_rutas()
            check("un gate sin raices se rechaza al construirlo", False, "no reventó")
        except ValueError:
            check("un gate sin raices se rechaza al construirlo", True)
    finally:
        shutil.rmtree(vault, ignore_errors=True)


def probar_hoja_se_sanea_y_queda_autocontenida() -> None:
    """
    La hoja se abre en el navegador y la escribe un modelo que leyo texto
    derivado de una grabacion. Lo que se prueba es que ningun resto de ese texto
    pueda ejecutar algo ni traer recursos de afuera, y que el diseño pedido
    (oscuro fijo, impresion en blanco y negro) no dependa del modelo.
    """
    print("\n== la hoja se sanea y queda autocontenida ==")
    import re

    from orquestador import hoja_html as h

    sucio = (
        '<section class="bloque" onclick="x()"><h2><span>Tema</span></h2>'
        "<script>alert(1)</script><style>body{display:none}</style>"
        '<div class="t form" style="background:url(http://a.b/c.png)"><h3>A1 &amp; B</h3>'
        '<p>ver <a href="https://a.b">esto</a><img src="x.png" onerror="x()">'
        '<iframe src="//a.b"></iframe></p>'
        '<svg viewBox="0 0 10 10" onload="x()"><defs><marker id="fl" refX="9">'
        '<path d="M0 0L9 5z"/></marker></defs>'
        '<line x1="0" y1="0" x2="9" y2="9" stroke="currentColor" marker-end="url(#fl)"/>'
        '<text x="1" y="1" fill="url(http://a.b)">P</text></svg>'
        '<math display="block"><mfrac><mi>a</mi><mi>b</mi></mfrac></math><mi>suelto</mi>'
        "</div></section>"
    )
    limpio = h.sanear_html(sucio)
    check("elimina script y su contenido", "<script" not in limpio and "alert" not in limpio)
    check("elimina style y su contenido", "<style" not in limpio and "display:none" not in limpio)
    check("elimina los atributos de evento", not re.search(r"\son\w+=", limpio), limpio)
    check("elimina el atributo style", 'style="' not in limpio)
    check("no deja nada que apunte afuera",
          "http" not in limpio and "//a.b" not in limpio and "<a " not in limpio
          and "<img" not in limpio and "<iframe" not in limpio, limpio)
    check("conserva el texto de lo que desenvuelve", "esto" in limpio and "suelto" in limpio)
    check("conserva el SVG con su viewBox bien escrito", '<svg viewBox="0 0 10 10">' in limpio)
    check("conserva la flecha local del grafico", 'marker-end="url(#fl)"' in limpio)
    check("conserva el MathML", "<mfrac><mi>a</mi><mi>b</mi></mfrac>" in limpio)
    check("no acepta MathML fuera de <math>", "<mi>suelto" not in limpio)
    check("el texto queda escapado", "A1 &amp; B" in limpio)

    trabajo = {"ramo": "TERMODINÁMICA", "numero_clase": 4, "fecha": "2026-08-27"}
    doc = h.armar_documento(trabajo, "Intervalos", limpio, "<div>tarjeta</div>", "nota.md")
    check("la cabecera sale de los datos del trabajo, no del modelo",
          "TERMODINÁMICA &middot; Clase 04 &middot; jueves 27 de agosto de 2026" in doc)
    check("siempre en modo oscuro, sin seguir la configuracion del sistema",
          "prefers-color-scheme" not in doc and "color-scheme:dark" in doc)
    check("trae la version de impresion que ahorra tinta", "@media print" in doc)
    check("ningun recurso externo en todo el documento",
          not re.search(r'(?:src|href)=["\']?(?:https?:)?//', doc)
          and "<script" not in doc and "<link" not in doc)
    check("la leyenda explica las tres marcas",
          all(m in doc for m in ("<b>CL</b>", "<b>?</b>", "<b>+</b>")))


def probar_hoja_no_niega_anuncios_que_la_nota_trae() -> None:
    """
    El .docx decia "el profesor no anuncio fechas ni evaluacion" siempre que
    los llamados llegaban en null, aunque la nota de aprendizaje si los traia.
    Paso en cuatro clases reales, entre ellas Sistemas del 01-09-2026, donde
    negaba el anuncio de la prueba del martes siguiente. La hoja no puede
    repetirlo.
    """
    print("\n== la hoja no niega anuncios que la nota si trae ==")
    from orquestador import hoja_html as h

    nota = (
        "# Aprendizaje - Duopolio\n\n## Lo que el profesor pidió\n\n### Avisos\n\n"
        '- **Prueba la próxima semana.** El profesor lo confirmó: "el próximo\n'
        '  martes".\n\n### Evaluación\n\n- **Capítulos 3 al 9, sin el 8.** Textual: "sin el 8".\n\n'
        "## La materia\n\nOtra cosa\n"
    )
    tarjeta = h.tarjeta_lo_que_pidio(nota, None)
    check("con llamados en null, la tarjeta sale de la nota",
          "Prueba la próxima semana" in tarjeta, tarjeta)
    check("une la viñeta que sigue en la linea de abajo",
          "próximo martes" in tarjeta and "próximo\n" not in tarjeta, tarjeta)
    check("conserva los subtitulos de la nota", "Avisos" in tarjeta and "Evaluación" in tarjeta)
    check("no se mete en la seccion siguiente", "Otra cosa" not in tarjeta)
    check("y nunca dice que no hubo anuncios", "no anunció" not in tarjeta)

    vacio = h.tarjeta_lo_que_pidio("", {"avisos": [], "evaluacion": []})
    check("llamados vacios y comprobados si pueden decir que no hubo anuncios",
          "no anunció" in vacio)

    desconocido = h.tarjeta_lo_que_pidio("", None)
    check("sin nota y sin llamados dice que no se pudo comprobar",
          "No se pudo comprobar" in desconocido)
    check("y no lo disfraza de 'no hubo anuncios'", "no anunció" not in desconocido)

    dudoso = h.tarjeta_lo_que_pidio(
        "", {"avisos": [{"que": "control", "textual": "el jueves", "seguro": False}], "evaluacion": []}
    )
    check("un llamado dudoso lleva la marca de verificar", 'class="f duda"' in dudoso)

    peligroso = h.tarjeta_lo_que_pidio(
        "## Lo que el profesor pidió\n\n- <script>x()</script> **ojo**\n\n## Fin", None
    )
    check("el texto de la nota se escapa",
          "<script>" not in peligroso and "&lt;script&gt;" in peligroso, peligroso)

    # Como escribe la skill en la practica: subtitulos en negrita en vez de ###,
    # puntos que declara no seguros y un callout de varias lineas. La primera
    # version juntaba los subtitulos arriba y todas las viñetas abajo, asi que
    # no se distinguia que entraba en la prueba y que era un aviso. Paso con
    # Desempeño Organizacional del 12-08 y del 26-08-2026.
    import re

    real = (
        "## Lo que el profesor pidió\n\n"
        "**Entra en evaluación:**\n\n"
        '- El control es sobre esta clase. Cita textual: "va a ser sobre\n'
        '  los mecanismos".\n\n'
        "**Avisos:**\n\n"
        "- Va a subir una lectura *(no seguro respecto del contenido exacto)*.\n"
        "- Solemne 1 entre el 7 y el 25. **(seguro: no)**\n\n"
        "> [!verificar] Las fechas quedaron poco claras\n"
        "> en el audio, confírmalas.\n\n"
        "## La materia\n"
    )
    t = h.tarjeta_lo_que_pidio(real, None)
    orden = [t.find("Entra en evaluación"), t.find("El control es sobre"),
             t.find("Avisos"), t.find("Va a subir una lectura")]
    check("respeta el orden de la nota: cada subtitulo antes de sus viñetas",
          -1 not in orden and orden == sorted(orden), str(orden))
    check("un subtitulo en negrita se muestra como subtitulo",
          '<span class="clave">Entra en evaluación</span>' in t, t)
    check("una viñeta que la nota declara no segura lleva la marca de verificar",
          re.search(r'lectura <i>\(no seguro[^<]*</i>\.<span class="f duda">', t) is not None
          and re.search(r'seguro: no\)</b><span class="f duda">', t) is not None, t)
    check("una viñeta sin dudas conserva la marca de la clase",
          re.search(r'mecanismos"\.<span class="f cl">', t) is not None, t)
    check("el callout de varias lineas queda en un solo parrafo",
          t.count('<p class="mini">') == 1 and "poco claras en el audio" in t, t)

    # La advertencia en negrita puede ir en la linea siguiente de su viñeta.
    # Tomarla como subtitulo le quitaba la duda a la viñeta y colgaba la
    # siguiente de un titulo falso (Desempeño Organizacional, 12-08-2026).
    continuacion = (
        "## Lo que el profesor pidió\n\n"
        "**Qué dijo que entra en evaluación**\n\n"
        '- La nota de presentación reemplazaría la del examen. Textual: "le repito esa nota".\n'
        "  **(seguro: no, el tramo del audio está cortado)**\n"
        "- En los casos se evalúa el argumento.\n\n"
        "## Fin\n"
    )
    t2 = h.tarjeta_lo_que_pidio(continuacion, None)
    check("una advertencia en negrita pegada a su viñeta no se vuelve subtitulo",
          t2.count('<span class="clave">') == 1, t2)
    check("y esa viñeta conserva la marca de verificar",
          re.search(r'cortado\)</b><span class="f duda">', t2) is not None, t2)
    check("la viñeta siguiente sigue en la misma lista, con su marca de clase",
          t2.count("<ul>") == 1 and re.search(r'argumento\.<span class="f cl">', t2) is not None, t2)

    # Un enlace de Obsidian no funciona fuera del vault. Salia con los corchetes
    # en la tarjeta de Desempeño Organizacional del 02-09-2026.
    enlace = h.tarjeta_lo_que_pidio(
        "## Lo que el profesor pidió\n\n"
        "En esta clase no hubo anuncios. Ver [[Aprendizaje - Clase anterior]] y "
        "[[Fuente - Otra clase|la fuente]].\n\n## Fin\n",
        None,
    )
    check("un enlace de Obsidian queda como el nombre de la nota, sin corchetes",
          "[[" not in enlace and "<i>Aprendizaje - Clase anterior</i>" in enlace
          and "<i>la fuente</i>" in enlace, enlace)


def probar_una_sola_frase_cuando_no_hubo_anuncios() -> None:
    """
    La skill copiaba sus propias reglas dentro de "Lo que el profesor pidio", y
    la hoja las mostraba tal cual en la tarjeta que mas se cree. Revisadas el
    14-09-2026, pasaba al menos en 12 de las 21 notas del semestre que traen la
    seccion, y en las cinco cuyos llamados vinieron vacios. En Desempeño
    Organizacional del 02-09 decia "Es una respuesta correcta y frecuente: no se
    rellena con suposiciones", y el 19-08 "Esta seccion queda sin contenido a
    proposito". Las otras formas eran justificar lo que no se listaba y mandar a
    revisar las notas de clases anteriores.

    El arreglo esta en la skill: da la frase exacta para el caso vacio y dice que
    sus reglas no son texto para la nota. No se filtra en Python, porque un
    filtro por patrones solo reconoce las formas ya vistas y la siguiente llega
    con otras palabras.

    Esta prueba fija que la frase de la skill sea la misma que la hoja escribe
    cuando la tarjeta sale de llamados vacios, para que el estudiante lea una
    sola version venga de donde venga la tarjeta.
    """
    print("\n== una sola frase cuando el profesor no anuncio nada ==")
    from orquestador import hoja_html as h

    frase = "En esta clase el profesor no anunció fechas, entregas ni contenidos de evaluación."
    skill = RAIZ / ".claude" / "skills" / "transcripciones-a-conocimiento" / "SKILL.md"
    check("la skill da la frase exacta para el caso sin anuncios",
          frase in skill.read_text(encoding="utf-8"))
    check("la hoja escribe esa misma frase cuando los llamados vienen vacios",
          frase in h.tarjeta_lo_que_pidio("", {"avisos": [], "evaluacion": []}))

    nota = f"## Lo que el profesor pidió\n\n{frase}\n\n## La materia\n\nOtra cosa\n"
    tarjeta = h.tarjeta_lo_que_pidio(nota, None)
    check("una nota con solo esa frase la muestra entera en la tarjeta", frase in tarjeta, tarjeta)
    check("y no la toma por algo que no se pudo comprobar",
          "No se pudo comprobar" not in tarjeta, tarjeta)


def probar_hoja_pule_usos_del_modelo() -> None:
    """
    Dos usos del modelo que se veian mal en la hoja de Desempeño Organizacional
    del 26-08-2026: un subtitulo usado como etiqueta de una frase, que dejaba la
    linea de abajo empezando con dos puntos, y la frase de que verificar metida
    dentro de la marca "?", que se imprime chica y en superindice.
    """
    print("\n== la hoja corrige usos del modelo que se ven mal ==")
    from orquestador import hoja_html as h

    etiqueta = '<p><span class="clave">Dato de delegación</span>: el área comercial autoriza descuentos.</p>'
    check("un subtitulo seguido de dos puntos pierde los dos puntos",
          h.pulir_cuerpo(etiqueta) == '<p><span class="clave">Dato de delegación</span>el área comercial autoriza descuentos.</p>',
          h.pulir_cuerpo(etiqueta))

    marca = '<p>No los desarrolla en esta clase.<span class="f duda">? revisa si los explica en la lectura</span></p>'
    pulida = h.pulir_cuerpo(marca)
    check("la frase sale de la marca y la marca queda solo con su signo",
          pulida == '<p>No los desarrolla en esta clase. Revisa si los explica en la lectura.<span class="f duda">?</span></p>',
          pulida)

    bien = ('<p>Dijo que entra.<span class="f cl">CL</span> Dudoso.<span class="f duda">?</span> '
            'Propio.<span class="f mas">+</span></p>')
    check("las marcas bien usadas no cambian", h.pulir_cuerpo(bien) == bien, h.pulir_cuerpo(bien))


def probar_hoja_degrada_sin_mentir() -> None:
    """
    Si la redaccion falla, la clase no se pierde y la hoja lo dice arriba. Y la
    etapa corre sin ninguna herramienta: recibe las notas en el prompt y
    devuelve texto, asi que no depende de que un gate este bien escrito.
    """
    print("\n== la hoja degrada sin mentir ==")
    import asyncio
    import inspect

    from orquestador import cancelacion
    from orquestador import finalizar_clase as fc
    from orquestador import hoja_html as h

    cuerpo_bueno = '<section class="bloque"><p>' + "materia " * 120 + "</p></section>"
    BUENA = f"{h.MARCA_INICIO}\n{cuerpo_bueno}\n{h.MARCA_FIN}"
    opciones_vistas = []

    def query_que_mira(mensajes):
        async def _query(*a, **kw):
            opciones_vistas.append(kw.get("options"))
            for m in mensajes:
                yield m
        return _query

    originales = (h.query, h.registrar_uso)
    h.registrar_uso = lambda *a, **kw: None
    try:
        argumentos = ("nota de aprendizaje", "nota de fuente", "", [], "TERMODINAMICA",
                      "Titulo", "2026-08-27", "s1")

        h.query = query_que_mira(_mensajes_sdk(BUENA, False))
        cuerpo, motivo = asyncio.run(h.redactar_cuerpo(*argumentos))
        check("una respuesta completa se acepta", cuerpo is not None and motivo is None, str(motivo))

        opciones = opciones_vistas[-1]
        check("la etapa no tiene ninguna herramienta permitida", opciones.allowed_tools == [])
        check("y prohibe explicitamente las que escriben, leen o ejecutan",
              {"Bash", "Read", "Write", "Edit"} <= set(opciones.disallowed_tools))
        check("no carga la configuracion del proyecto", opciones.setting_sources == [])

        h.query = query_que_mira(_mensajes_sdk(BUENA, True, api_error_status=529))
        cuerpo, motivo = asyncio.run(h.redactar_cuerpo(*argumentos))
        check("un error de la API despues de entregar la hoja no la descarta",
              cuerpo is not None, str(motivo))

        h.query = query_que_mira(_mensajes_sdk("no alcance", True, api_error_status=429))
        cuerpo, motivo = asyncio.run(h.redactar_cuerpo(*argumentos))
        check("sin la hoja no hay cuerpo", cuerpo is None)
        check("y el motivo nombra el problema de conexion", bool(motivo) and "429" in motivo, str(motivo))

        h.query = query_que_mira(
            _mensajes_sdk(f"{h.MARCA_INICIO}\n<p>casi nada</p>\n{h.MARCA_FIN}", False)
        )
        cuerpo, motivo = asyncio.run(h.redactar_cuerpo(*argumentos))
        check("una hoja casi vacia se trata como falla",
              cuerpo is None and "vacía" in (motivo or ""), str(motivo))

        antes = len(opciones_vistas)
        cuerpo, motivo = asyncio.run(h.redactar_cuerpo("", "", "", [], "X", "T", "2026-01-01", "s2"))
        check("sin notas no gasta una llamada al modelo",
              len(opciones_vistas) == antes and cuerpo is None)
    finally:
        h.query, h.registrar_uso = originales

    doc = h.armar_documento({"ramo": "X", "numero_clase": 1, "fecha": "2026-08-27"},
                            "T", None, "", "", "se corto", "s9")
    check("la hoja degradada avisa que falta la materia", "Falta la materia condensada" in doc)
    check("y aclara que eso no significa que la clase no tenga materia",
          "no significa que la clase no tenga materia" in doc)

    # El envoltorio de finalizar_clase degrada ante cualquier falla, salvo el
    # aborto pedido desde la barra de menu, que tiene que seguir subiendo.
    avisos = []
    originales_fc = (fc.redactar_cuerpo, fc.notificar_aviso)
    fc.notificar_aviso = lambda t, c: avisos.append((t, c))
    try:
        async def revienta(*a, **kw):
            raise RuntimeError("fallo inventado")
        fc.redactar_cuerpo = revienta
        cuerpo, motivo = asyncio.run(fc._redactar_hoja("a", "f", "", [], "R", "T", "2026-01-01", "s"))
        check("una falla de la redaccion no tira la clase",
              cuerpo is None and "RuntimeError" in (motivo or ""), str(motivo))
        check("y avisa al estudiante", len(avisos) == 1, str(avisos))

        async def aborta(*a, **kw):
            raise cancelacion.Abortado()
        fc.redactar_cuerpo = aborta
        try:
            asyncio.run(fc._redactar_hoja("a", "f", "", [], "R", "T", "2026-01-01", "s"))
            check("un aborto pedido no se traga", False, "no subio")
        except cancelacion.Abortado:
            check("un aborto pedido no se traga", True)
    finally:
        fc.redactar_cuerpo, fc.notificar_aviso = originales_fc

    fuente = inspect.getsource(fc.procesar_clase_reconocida)
    check("la redaccion va antes de la seccion critica, que no se puede abortar",
          0 <= fuente.find("_redactar_hoja(") < fuente.find("seccion_critica()"))
    check("el pipeline ya no arma el .docx ni agrega a Anki",
          "generar_docx" not in fuente and "anki_connect" not in fuente
          and "extraer_preguntas_respuestas" not in fuente)


def probar_renumerar_corrige_la_hoja() -> None:
    """
    En los ramos con numeracion por orden, una clase mas antigua que llega tarde
    corre el numero de las siguientes. El nombre del archivo ya se corregia,
    pero la hoja lleva el numero tambien escrito en la cabecera.
    """
    print("\n== renumerar corrige tambien la cabecera de la hoja ==")
    with tempfile.TemporaryDirectory() as tmp:
        procesados, output = Path(tmp) / "Procesados", Path(tmp) / "Output"
        (procesados / "RAMO").mkdir(parents=True)
        (output / "RAMO").mkdir(parents=True)
        (procesados / "RAMO" / "Clase 01 - 2026-08-03 - Primera.m4a").write_bytes(b"a")
        (procesados / "RAMO" / "Clase 01 - 2026-08-10 - Segunda.m4a").write_bytes(b"a")
        hoja = output / "RAMO" / "Clase 01 - 2026-08-10 - Segunda.html"
        hoja.write_text(
            '<p class="ramo">RAMO &middot; Clase 01 &middot; lunes</p><p>lo vimos en la Clase 01</p>',
            encoding="utf-8",
        )
        nombres.renumerar_clases_ramo(procesados, output, "RAMO")
        nueva = output / "RAMO" / "Clase 02 - 2026-08-10 - Segunda.html"
        check("la hoja se renombra", nueva.is_file() and not hoja.exists())
        texto = nueva.read_text(encoding="utf-8") if nueva.is_file() else ""
        check("y su cabecera dice el numero nuevo", "&middot; Clase 02 &middot;" in texto, texto)
        check("sin tocar la materia que menciona el numero viejo",
              "lo vimos en la Clase 01" in texto, texto)


def probar_clase_completa_termina_en_notas_y_hoja() -> None:
    """
    Desde el 14-09-2026 una clase termina en dos cosas y nada mas: las notas en
    Obsidian y la hoja HTML. Anki y el .docx salieron del pipeline. Esto corre
    procesar_clase_reconocida entera en un sandbox de ensayo, con las tres
    llamadas al modelo reemplazadas por respuestas fijas, para comprobar sin
    gastar cuota que la cadena completa sigue cerrando sin ellos.
    """
    print("\n== una clase completa termina en notas y hoja, sin Anki ni .docx ==")
    import asyncio
    import importlib.util

    from orquestador import estado_vivo as ev
    from orquestador import finalizar_clase as fc

    for retirado in ("anki_connect", "dialogo_anki", "extraer_flashcards", "docx_generator",
                     "formulas", "mapa_visual", "regenerar", "procesar_aparte"):
        check(f"el modulo {retirado} ya no existe",
              importlib.util.find_spec(f"orquestador.{retirado}") is None)
    check("la barra de menu cuenta cuatro pasos",
          len(ev.PASOS) == 4 and not hasattr(ev, "PASO_ANKI"), str(ev.PASOS))

    base = Path(tempfile.mkdtemp(prefix="clase_completa_"))
    ramo = "RAMO DE PRUEBA"
    carpeta = base / "vault" / ramo
    carpeta.mkdir(parents=True)
    audio = base / "Input" / "clase.m4a"
    audio.parent.mkdir()
    audio.write_bytes(b"audio de mentira")
    pendientes = base / "pendientes"
    pendientes.mkdir()
    texto = pendientes / "s1.txt"
    texto.write_text("transcripcion de mentira", encoding="utf-8")

    config = {
        "rutas": {"vault_obsidian": str(base / "vault"), "output": str(base / "Output"),
                  "procesados": str(base / "Procesados")},
        "carpetas_ramo": {},
        ensayo.CLAVE: True,
    }
    trabajo = {"slug": "s1", "fecha": "2026-09-09", "ramo": ramo, "numero_clase": 6,
               "archivo_texto": str(texto), "archivos_originales": [str(audio)],
               "reconocido": True}

    async def skill_falsa(*a, **kw):
        aprendizaje = carpeta / "Aprendizaje - Clase de prueba.md"
        aprendizaje.write_text(
            "# Aprendizaje\n\n## Lo que el profesor pidió\n\n"
            '- Hay control el jueves. Textual: "el jueves hay control".\n\n'
            "## La materia\n\nAlgo que estudiar.\n", encoding="utf-8")
        fuente = carpeta / "Fuente - Clase de prueba.md"
        fuente.write_text("# Fuente\n\nLo que se dijo.\n", encoding="utf-8")
        return {"titulo": "Una clase de prueba", "fuente": str(fuente),
                "aprendizaje": str(aprendizaje), "contexto": "",
                "conceptos_repetidos": [], "llamados": None}

    async def revision_falsa(*a, **kw):
        return {"veredicto": "aprobado", "hallazgos": []}

    cuerpo = ('<section class="bloque"><h2><span>Tema</span></h2><div class="rejilla">'
              '<div class="t con"><h3><span class="n">A1</span>Idea</h3><p>'
              + "palabra " * 120 + '<span class="f cl">CL</span></p></div></div></section>')

    async def hoja_falsa(*a, **kw):
        return cuerpo, None

    pasos, avisos = [], []
    originales = (fc.aplicar_skill, fc.revisar, fc.redactar_cuerpo, fc.notificar_progreso,
                  fc.notificar_aviso, fc.notificar_exito, ev.fijar_clase)
    fc.aplicar_skill, fc.revisar, fc.redactar_cuerpo = skill_falsa, revision_falsa, hoja_falsa
    fc.notificar_progreso = lambda paso, detalle="": pasos.append((paso, detalle))
    fc.notificar_aviso = lambda titulo, mensaje: avisos.append((titulo, mensaje))
    fc.notificar_exito = lambda *a, **kw: None
    ev.fijar_clase = lambda nombre: None
    usar_dir_pendientes(pendientes)
    try:
        ruta = asyncio.run(fc.procesar_clase_reconocida(trabajo, config))
        check("deja la hoja en Output, con el nombre de la clase",
              ruta.is_file() and ruta.name == "Clase 06 - 2026-09-09 - Una clase de prueba.html",
              str(ruta))
        hoja = ruta.read_text(encoding="utf-8") if ruta.is_file() else ""
        check("la hoja trae la materia y lo que pidio el profesor",
              "palabra palabra" in hoja and "Hay control el jueves" in hoja)
        check("las notas quedan en la carpeta del ramo en el vault",
              (carpeta / "Aprendizaje - Clase de prueba.md").is_file())
        archivados = list((base / "Procesados" / ramo).glob("Clase 06 - 2026-09-09 - *.m4a"))
        check("el audio se archiva (en ensayo se copia)",
              len(archivados) == 1 and audio.is_file(), str(archivados))
        check("no se crea ningun .docx", not list(base.rglob("*.docx")))
        check("ningun paso ni aviso habla de Anki o de flashcards",
              not any(p in str(x).lower() for x in pasos + avisos for p in ("anki", "flashcard")),
              str(pasos + avisos))
        check("y no hubo avisos", avisos == [], str(avisos))
    finally:
        (fc.aplicar_skill, fc.revisar, fc.redactar_cuerpo, fc.notificar_progreso,
         fc.notificar_aviso, fc.notificar_exito, ev.fijar_clase) = originales
        usar_dir_pendientes(None)
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    probar_nombres()
    probar_deteccion()
    probar_aislamiento_del_ensayo()
    probar_archivado_no_destructivo()
    probar_dialogo_nunca_descarta_solo()
    probar_el_nombre_del_archivo_manda_sobre_el_dia()
    probar_pantalla_de_confirmacion()
    probar_decisiones_de_pantalla_se_aplican()
    probar_bitacora_deshace_todo()
    probar_bitacora_no_borra_lo_ajeno()
    probar_seccion_critica()
    probar_audio_largo_se_corta_solo()
    probar_el_borrado_no_alcanza_tus_carpetas()
    probar_dos_clases_no_se_fusionan()
    probar_las_notificaciones_no_se_pierden()
    probar_error_de_sesion_se_explica()
    probar_titulo_nunca_falta()
    probar_gate_de_rutas()
    probar_error_del_sdk_se_explica()
    probar_error_tardio_no_tira_el_trabajo()
    probar_revision_fallida_no_dice_aprobado()
    probar_una_sola_comprobacion_de_vault()
    probar_hoja_se_sanea_y_queda_autocontenida()
    probar_hoja_no_niega_anuncios_que_la_nota_trae()
    probar_una_sola_frase_cuando_no_hubo_anuncios()
    probar_hoja_degrada_sin_mentir()
    probar_hoja_pule_usos_del_modelo()
    probar_renumerar_corrige_la_hoja()
    probar_clase_completa_termina_en_notas_y_hoja()

    print()
    if fallos:
        print(f"FALLARON {len(fallos)}: " + ", ".join(fallos))
        raise SystemExit(1)
    print("Todas las pruebas pasaron.")

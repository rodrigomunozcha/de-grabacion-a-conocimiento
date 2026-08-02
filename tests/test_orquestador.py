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

        docx = base / "salida.docx"
        docx.write_bytes(b"docx")
        b.archivo_creado(docx)

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
        check("el .docx se borro", not docx.exists())
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


def probar_formulas() -> None:
    print("\n== formulas con subindices y superindices reales ==")
    from docx import Document as Doc
    from orquestador import formulas

    check("reconoce una formula destacada", formulas.es_formula_destacada("$$x̄ ± σ$$"))
    check("no confunde texto normal con formula", not formulas.es_formula_destacada("cuesta $5 o $8"))
    check("extrae el contenido", formulas.texto_de_formula_destacada("$$x̄$$") == "x̄")

    tmp = Path(tempfile.mkdtemp())
    try:
        # Una formula destacada se dibuja como imagen, con tipografia
        # matematica de verdad (barra de fraccion, radical que se estira).
        doc = Doc()
        formulas.agregar_formula_destacada(
            doc, r"\bar{x} \pm z_{1-\alpha/2} \cdot \frac{\sigma}{\sqrt{n}}")
        ruta = Path(tmp) / "conformula.docx"
        doc.save(str(ruta))
        check("la formula destacada queda como imagen",
              len(Doc(str(ruta)).inline_shapes) == 1,
              f"imagenes={len(Doc(str(ruta)).inline_shapes)}")

        # Si el dibujo falla, no se pierde la formula: se escribe como texto.
        original = formulas._renderizar_imagen
        formulas._renderizar_imagen = lambda _l: None
        try:
            doc_fb = Doc()
            formulas.agregar_formula_destacada(doc_fb, "s^{2} = Σ(x_i - x̄)^{2}")
            p = doc_fb.paragraphs[-1]
            check("sin imagen se cae a texto con superindices",
                  [r.text for r in p.runs if r.font.superscript] == ["2", "2"])
            check("sin imagen se cae a texto con subindices",
                  [r.text for r in p.runs if r.font.subscript] == ["i"])
            check("y conserva los simbolos Unicode", "Σ" in p.text and "x̄" in p.text)
        finally:
            formulas._renderizar_imagen = original

        # Una formula corta dentro de una frase sigue siendo texto: una imagen
        # ahi quedaria desalineada con el renglon.
        doc2 = Doc()
        par = doc2.add_paragraph()
        from orquestador.docx_generator import _agregar_texto_con_negritas
        _agregar_texto_con_negritas(par, "La varianza $s^{2}$ usa **n-1** abajo.")
        check("la formula inline se formatea",
              [r.text for r in par.runs if r.font.superscript] == ["2"])
        check("la negrita sigue funcionando junto a la formula",
              any(r.bold and r.text == "n-1" for r in par.runs))
        check("un guion bajo suelto fuera de $ no se toca",
              "_" in _texto_render(doc2, "archivo_de_prueba.txt"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _texto_render(doc, texto: str) -> str:
    from orquestador.docx_generator import _agregar_texto_con_negritas
    p = doc.add_paragraph()
    _agregar_texto_con_negritas(p, texto)
    return p.text


def probar_contexto_va_primero() -> None:
    """El contexto solo sirve si se lee antes de la clase, o sea si esta al
    principio del documento."""
    print("\n== la seccion de contexto va al frente ==")
    from docx import Document as Doc

    tmp = Path(tempfile.mkdtemp())
    try:
        ruta = docx_generator.generar_docx(
            {"numero_clase": 1, "fecha": "2026-08-05", "ramo": "R"},
            "Titulo", "# Fuente\ntexto", "# Aprendizaje\ntexto",
            [{"concepto": "C", "por_que": "p"}],
            {"rutas": {"output": str(tmp)}},
            "# Contexto previo\n\nAlgo que hay que saber antes.",
        )
        encabezados = [p.text for p in Doc(str(ruta)).paragraphs
                       if p.style.name.startswith("Heading") and p.text.strip()]
        check("aparece la seccion de contexto",
              any("Antes de empezar" in h for h in encabezados), str(encabezados))
        check("va antes que los conceptos repetidos",
              encabezados.index("Antes de empezar: lo que conviene tener claro")
              < next(i for i, h in enumerate(encabezados) if "repetidos" in h))

        # Sin contexto el documento se arma igual: la seccion es opcional.
        ruta2 = docx_generator.generar_docx(
            {"numero_clase": 2, "fecha": "2026-08-06", "ramo": "R"},
            "Otro", "# Fuente\ntexto", "# Aprendizaje\ntexto", [],
            {"rutas": {"output": str(tmp)}}, "",
        )
        sin = [p.text for p in Doc(str(ruta2)).paragraphs if p.style.name.startswith("Heading")]
        check("sin contexto el .docx se arma igual",
              ruta2.is_file() and not any("Antes de empezar" in h for h in sin))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def probar_formulas_en_tablas() -> None:
    """
    Las celdas se escribian como texto plano, asi que la tabla de "que formula
    uso en cada caso" era el unico lugar del documento donde las formulas se
    veian crudas, con el guion bajo y los parentesis a la vista.
    """
    print("\n== formulas dentro de tablas ==")
    from docx import Document as Doc
    from orquestador import formulas

    check("una celda que es toda formula se reconoce",
          formulas.parece_solo_formula("x̄ ± z_(1-α/2)·σ/√n"))
    check("una celda de texto normal no se confunde con formula",
          not formulas.parece_solo_formula(
              "Quiero estimar μ y conozco σ (dato del enunciado)"))

    # El modelo no siempre escribe LaTeX: hay que entender su Unicode.
    latex = formulas.a_latex("p̂ ± z_(1-α/2)·√(p̂q̂/n)")
    check("el sombrero Unicode pasa a LaTeX", r"\hat{p}" in latex, latex)
    check("la raiz Unicode pasa a LaTeX", r"\sqrt{" in latex, latex)
    check("el subindice con parentesis pasa a llaves", "_{1-" in latex, latex)
    check("lo que ya viene en LaTeX no se toca",
          formulas.a_latex(r"\bar{x} \pm \sigma") == r"\bar{x} \pm \sigma")

    md = (
        "| Situación | Fórmula |\n"
        "|---|---|\n"
        "| Conozco σ, muestra grande | x̄ ± z_(1-α/2)·σ/√n |\n"
    )
    tmp = Path(tempfile.mkdtemp())
    try:
        ruta = docx_generator.generar_docx(
            {"numero_clase": 1, "fecha": "2026-08-05", "ramo": "R"},
            "T", "", "# A\n\n" + md, [], {"rutas": {"output": str(tmp)}}, "",
        )
        doc = Doc(str(ruta))
        marca = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline"
        imagenes_en_celdas = sum(
            len(p._p.findall(f".//{marca}"))
            for t in doc.tables for f in t.rows for c in f.cells for p in c.paragraphs
        )
        check("la formula de la celda se dibuja", imagenes_en_celdas == 1,
              f"imagenes={imagenes_en_celdas}")
        textos = [c.text for t in doc.tables for f in t.rows for c in f.cells]
        check("ya no queda la formula cruda en el texto",
              not any("z_(1-" in x for x in textos), str(textos))
        check("la celda de texto normal sigue siendo texto",
              any("Conozco σ" in x for x in textos), str(textos))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def probar_matematica_dentro_de_frases() -> None:
    """
    El modelo mete formulas en medio de las frases sin delimitarlas. Pedirle
    que las marque ya fallo, asi que se reconocen solas, pero sin arrastrar
    palabras normales que llevan guion bajo.
    """
    print("\n== subindices en medio de una frase ==")
    from docx import Document as Doc
    from orquestador.docx_generator import _agregar_texto_con_negritas

    doc = Doc()
    p = doc.add_paragraph()
    _agregar_texto_con_negritas(
        p, "el valor crítico que se busca en tabla (z_(1-α/2) o t_(n-1, 1-α/2))")
    subs = [r.text for r in p.runs if r.font.subscript]
    check("los dos subindices se aplican", subs == ["1-α/2", "n-1, 1-α/2"], str(subs))
    check("ya no queda la notacion cruda", "_(" not in p.text, p.text)

    # Lo que NO debe tocarse.
    for texto in ("El archivo_de_prueba.txt quedó guardado",
                  "usa snake_case para nombrar variables"):
        p2 = doc.add_paragraph()
        _agregar_texto_con_negritas(p2, texto)
        check(f"no toca '{texto[:22]}...'",
              not [r for r in p2.runs if r.font.subscript] and p2.text == texto)

    # La negrita convive con la matematica.
    p3 = doc.add_paragraph()
    _agregar_texto_con_negritas(p3, "usa **z_(α/2)** para el margen")
    check("negrita y subindice a la vez",
          any(r.bold and r.font.subscript for r in p3.runs))


def probar_mapa_y_secciones() -> None:
    """El mapa se dibuja de verdad, y la sesion por bloques de tiempo cede su
    lugar en el .docx a la materia ya digerida."""
    print("\n== mapa dibujado y secciones del .docx ==")
    from docx import Document as Doc

    aprendizaje = (
        "# Aprendizaje\n\n"
        "## 5. Materia lista para estudiar\nExplicacion con ejemplos.\n\n"
        "## Sesión de estudio de 90 minutos\nESTO_NO_VA_AL_DOCX\n\n"
        "## Mapa visual\n"
        "```mapa\n"
        '{"centro": "Tema", "ramas": [{"titulo": "Rama A", "puntos": ["p1", "p2"]},'
        ' {"titulo": "Rama B", "puntos": ["p3"]}]}\n'
        "```\n"
    )
    tmp = Path(tempfile.mkdtemp())
    try:
        ruta = docx_generator.generar_docx(
            {"numero_clase": 1, "fecha": "2026-08-05", "ramo": "R"},
            "T", "# Fuente\ntexto", aprendizaje, [], {"rutas": {"output": str(tmp)}}, "",
        )
        doc = Doc(str(ruta))
        texto = "\n".join(p.text for p in doc.paragraphs)
        encabezados = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]

        check("la sesion por bloques no va al .docx", "ESTO_NO_VA_AL_DOCX" not in texto)
        check("la materia lista para estudiar si va",
              any("Materia lista para estudiar" in h for h in encabezados))
        check("el mapa se inserta como imagen", len(doc.inline_shapes) == 1,
              f"imagenes={len(doc.inline_shapes)}")
        check("no se duplica el titulo del mapa",
              sum(1 for h in encabezados if "mapa" in h.lower()) == 1,
              str([h for h in encabezados if "mapa" in h.lower()]))
        check("el bloque de datos crudo no se imprime", '"centro"' not in texto)

        # Datos mal formados: el documento se arma igual, sin mapa.
        malo = "# A\n\n## Mapa visual\n```mapa\nesto no es json\n```\n"
        r2 = docx_generator.generar_docx(
            {"numero_clase": 2, "fecha": "2026-08-06", "ramo": "R"},
            "T2", "", malo, [], {"rutas": {"output": str(tmp)}}, "",
        )
        check("un mapa mal formado no rompe el documento",
              r2.is_file() and len(Doc(str(r2)).inline_shapes) == 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def probar_aviso_anki() -> None:
    print("\n== aviso cuando Anki esta cerrado ==")
    from orquestador import anki_connect, dialogo_anki

    original = anki_connect.verificar_conexion
    original_preg = dialogo_anki._preguntar
    try:
        anki_connect.verificar_conexion = lambda: True
        pregunto = []
        dialogo_anki._preguntar = lambda reintento=False: pregunto.append(1) or dialogo_anki.OPCION_SEGUIR
        sigue = dialogo_anki.confirmar_antes_de_empezar()
        check("con Anki abierto no molesta con ningun dialogo", sigue and not pregunto)

        anki_connect.verificar_conexion = lambda: False
        dialogo_anki._preguntar = lambda reintento=False: dialogo_anki.OPCION_SEGUIR
        check("'continuar sin Anki' deja procesar", dialogo_anki.confirmar_antes_de_empezar())

        # Dice que ya lo abrio pero sigue cerrado: se vuelve a comprobar en vez
        # de creerle, y despues de unos intentos se sigue igual.
        veces = []
        dialogo_anki._preguntar = lambda reintento=False: (veces.append(reintento)
                                                           or dialogo_anki.OPCION_YA_ABRI)
        check("'ya lo abri' con Anki aun cerrado no bloquea",
              dialogo_anki.confirmar_antes_de_empezar())
        check("reintenta y avisa que sigue sin detectarlo",
              len(veces) == dialogo_anki.INTENTOS_MAXIMOS and veces[1] is True, str(veces))
    finally:
        anki_connect.verificar_conexion = original
        dialogo_anki._preguntar = original_preg


if __name__ == "__main__":
    probar_nombres()
    probar_deteccion()
    probar_flashcards()
    probar_docx()
    probar_aislamiento_del_ensayo()
    probar_archivado_no_destructivo()
    probar_dialogo_nunca_descarta_solo()
    probar_bitacora_deshace_todo()
    probar_bitacora_no_borra_lo_ajeno()
    probar_seccion_critica()
    probar_formulas()
    probar_contexto_va_primero()
    probar_formulas_en_tablas()
    probar_matematica_dentro_de_frases()
    probar_mapa_y_secciones()
    probar_aviso_anki()

    print()
    if fallos:
        print(f"FALLARON {len(fallos)}: " + ", ".join(fallos))
        raise SystemExit(1)
    print("Todas las pruebas pasaron.")

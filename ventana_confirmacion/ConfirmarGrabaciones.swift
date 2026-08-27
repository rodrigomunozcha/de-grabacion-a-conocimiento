// Ventana que muestra todas las grabaciones de Input antes de procesarlas,
// con lo que el sistema detecto de cada una, y deja corregirlo.
//
// Por que existe. El dialogo anterior preguntaba por una grabacion a la vez,
// dentro del bucle que las procesa: con dos dudosas eran dos interrupciones
// separadas por 20 minutos de transcripcion, y la segunda llegaba cuando el
// estudiante ya se habia ido. Aca todo se pregunta junto, en los primeros
// segundos, mientras todavia esta frente al Mac por el clic que acaba de dar.
//
// Por que en Swift. Una lista con un menu por fila necesita AppKit. Desde
// Python eso obliga a PyObjC o rumps, dependencias grandes para una ventana.
// swiftc ya viene con las herramientas de linea de comandos de Xcode. Mismo
// criterio que barra_menu/BarraEstado.swift.
//
// Contrato con el pipeline: lee un JSON por stdin, escribe un JSON por stdout.
// No toca archivos, no mueve audios, no le habla al pipeline de otra forma.
// Si se cae o nunca abre, orquestador/pantalla_confirmacion.py cae solo al
// comportamiento de siempre. Por eso este binario puede morir de forma abrupta
// sin dejar nada inconsistente: no hay estado que mantener.
//
// El tiempo se acaba a los 10 minutos y eso NO descarta nada: equivale a
// cerrar la ventana, y quien decide que significa eso es el lado Python.
//
// Compilar con: bash boton_app/compilar_apps.sh

import Cocoa

// MARK: - Contrato con Python

struct Grabacion: Decodable {
    let clave: String
    let archivos: [String]
    let fecha: String
    let diaSemana: String
    let duracionMin: Int?
    let ramo: String?
    let reconocido: Bool
    let origen: String?

    enum CodingKeys: String, CodingKey {
        case clave, archivos, fecha, ramo, reconocido, origen
        case diaSemana = "dia_semana"
        case duracionMin = "duracion_min"
    }
}

struct Entrada: Decodable {
    let grabaciones: [Grabacion]
    let ramos: [String]
    let timeoutSegundos: Double

    enum CodingKeys: String, CodingKey {
        case grabaciones, ramos
        case timeoutSegundos = "timeout_segundos"
    }
}

struct Decision: Encodable {
    let clave: String
    let queHacer: String
    let ramo: String?
    let ramoNuevo: Bool

    enum CodingKeys: String, CodingKey {
        case clave, ramo
        case queHacer = "que_hacer"
        case ramoNuevo = "ramo_nuevo"
    }
}

struct Salida: Encodable {
    let accion: String
    let decisiones: [Decision]
}

// Las mismas constantes que pantalla_confirmacion.py. Si cambian alla, cambian
// aca: son un contrato entre dos procesos, no dos listas independientes.
let ACCION_PROCESAR = "procesar"
let ACCION_SOLO_TRANSCRIBIR = "solo_transcribir"
let ACCION_OMITIR = "omitir"

// Entradas del menu que no son un ramo. Van al final, despues de un separador.
let OPCION_NO_ES_CLASE = "No es una clase (solo transcribir)"
let OPCION_OTRO_RAMO = "Otro ramo..."
let OPCION_OMITIR = "Dejarla para después"

// MARK: - Estado de una fila

/// Lo que el estudiante eligio para una grabacion. Arranca en lo que el
/// sistema detecto, asi que no tocar nada equivale a aceptar lo propuesto.
final class FilaEstado {
    let grabacion: Grabacion
    var seleccion: String
    var ramoEscrito: String = ""

    init(_ g: Grabacion) {
        grabacion = g
        // Sin ramo detectado la fila arranca sin elegir, para que se note que
        // pide una decision en vez de traer una respuesta puesta por defecto.
        seleccion = g.ramo ?? OPCION_NO_ES_CLASE
    }

    var decision: Decision {
        switch seleccion {
        case OPCION_OMITIR:
            return Decision(clave: grabacion.clave, queHacer: ACCION_OMITIR,
                            ramo: nil, ramoNuevo: false)
        case OPCION_NO_ES_CLASE:
            return Decision(clave: grabacion.clave, queHacer: ACCION_SOLO_TRANSCRIBIR,
                            ramo: nil, ramoNuevo: false)
        case OPCION_OTRO_RAMO:
            let nombre = ramoEscrito.trimmingCharacters(in: .whitespacesAndNewlines)
            // Un nombre vacio no puede archivar nada: se trata como omitir.
            if nombre.isEmpty {
                return Decision(clave: grabacion.clave, queHacer: ACCION_OMITIR,
                                ramo: nil, ramoNuevo: false)
            }
            return Decision(clave: grabacion.clave, queHacer: ACCION_PROCESAR,
                            ramo: nombre, ramoNuevo: true)
        default:
            return Decision(clave: grabacion.clave, queHacer: ACCION_PROCESAR,
                            ramo: seleccion, ramoNuevo: false)
        }
    }
}

// MARK: - Ventana

final class Controlador: NSObject, NSApplicationDelegate, NSWindowDelegate {
    private let entrada: Entrada
    private var filas: [FilaEstado] = []
    private var ventana: NSWindow!
    private var temporizador: Timer?
    private var restante: Double
    private var etiquetaTiempo: NSTextField!

    init(entrada: Entrada) {
        self.entrada = entrada
        self.restante = entrada.timeoutSegundos
        self.filas = entrada.grabaciones.map(FilaEstado.init)
    }

    func applicationDidFinishLaunching(_ n: Notification) {
        construirVentana()
        NSApp.activate(ignoringOtherApps: true)
        temporizador = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            self?.tick()
        }
    }

    private func tick() {
        restante -= 1
        if restante <= 0 {
            // Vencer el tiempo equivale a cerrar la ventana: no decide nada.
            terminar(accion: "timeout")
            return
        }
        // El aviso aparece recien en el ultimo minuto. Antes de eso, una cuenta
        // regresiva permanente solo mete prisa sin aportar nada.
        if restante <= 60 {
            let s = Int(restante)
            etiquetaTiempo.stringValue = "Si no eliges nada, en \(s)s se procesan las reconocidas y el resto queda para después."
            etiquetaTiempo.isHidden = false
        }
    }

    private func construirVentana() {
        let ancho: CGFloat = 660
        let altoFila: CGFloat = 74
        let alto = min(620, 190 + CGFloat(filas.count) * altoFila)

        ventana = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: ancho, height: alto),
            styleMask: [.titled, .closable],
            backing: .buffered, defer: false)
        ventana.title = "Grabaciones por procesar"
        ventana.delegate = self
        ventana.center()

        let contenido = NSView(frame: ventana.contentView!.bounds)
        contenido.autoresizingMask = [.width, .height]

        let titulo = NSTextField(labelWithString:
            filas.count == 1 ? "Encontré 1 grabación en Input"
                             : "Encontré \(filas.count) grabaciones en Input")
        titulo.font = .systemFont(ofSize: 15, weight: .semibold)
        titulo.frame = NSRect(x: 20, y: alto - 42, width: ancho - 40, height: 22)
        contenido.addSubview(titulo)

        let bajada = NSTextField(labelWithString:
            "Revisa a qué ramo va cada una. Lo que ya está bien no necesita que toques nada.")
        bajada.font = .systemFont(ofSize: 12)
        bajada.textColor = .secondaryLabelColor
        bajada.frame = NSRect(x: 20, y: alto - 62, width: ancho - 40, height: 18)
        contenido.addSubview(bajada)

        // Las filas van dentro de un scroll: con seis grabaciones la ventana
        // no puede crecer hasta salirse de la pantalla.
        let areaAlto = alto - 150
        let scroll = NSScrollView(frame: NSRect(x: 12, y: 62, width: ancho - 24, height: areaAlto))
        scroll.hasVerticalScroller = true
        scroll.drawsBackground = false
        scroll.autohidesScrollers = true

        let interiorAlto = max(areaAlto, CGFloat(filas.count) * altoFila)
        let interior = NSView(frame: NSRect(x: 0, y: 0, width: ancho - 24, height: interiorAlto))

        for (i, fila) in filas.enumerated() {
            let y = interiorAlto - CGFloat(i + 1) * altoFila
            interior.addSubview(construirFila(fila, indice: i, y: y, ancho: ancho - 24))
        }
        scroll.documentView = interior
        contenido.addSubview(scroll)

        etiquetaTiempo = NSTextField(labelWithString: "")
        etiquetaTiempo.font = .systemFont(ofSize: 11)
        etiquetaTiempo.textColor = .secondaryLabelColor
        etiquetaTiempo.frame = NSRect(x: 20, y: 20, width: ancho - 240, height: 32)
        etiquetaTiempo.isHidden = true
        etiquetaTiempo.maximumNumberOfLines = 2
        contenido.addSubview(etiquetaTiempo)

        let procesar = NSButton(title: "Procesar", target: self, action: #selector(alProcesar))
        procesar.bezelStyle = .rounded
        procesar.keyEquivalent = "\r"
        procesar.frame = NSRect(x: ancho - 120, y: 18, width: 100, height: 32)
        contenido.addSubview(procesar)

        let cancelar = NSButton(title: "Cancelar", target: self, action: #selector(alCancelar))
        cancelar.bezelStyle = .rounded
        cancelar.keyEquivalent = "\u{1b}"
        cancelar.frame = NSRect(x: ancho - 216, y: 18, width: 92, height: 32)
        contenido.addSubview(cancelar)

        ventana.contentView = contenido
        ventana.makeKeyAndOrderFront(nil)
    }

    private func construirFila(_ fila: FilaEstado, indice: Int, y: CGFloat, ancho: CGFloat) -> NSView {
        let vista = NSView(frame: NSRect(x: 0, y: y, width: ancho, height: 74))

        // Coordenadas de abajo hacia arriba dentro de los 74 puntos de la fila:
        // menu 6-30, detalle 32-48, nombre 50-68, separador 73. Se escriben
        // asi para que se vea de un vistazo que nada se sale ni se pisa con la
        // fila siguiente (el menu estaba en y=-2 y sobresalia por abajo).
        let g = fila.grabacion
        let nombre = NSTextField(labelWithString: g.archivos.joined(separator: ", "))
        nombre.font = .systemFont(ofSize: 13, weight: .medium)
        nombre.lineBreakMode = .byTruncatingMiddle
        nombre.frame = NSRect(x: 12, y: 50, width: ancho - 24, height: 18)
        vista.addSubview(nombre)

        var detalle = "\(g.diaSemana) \(g.fecha)"
        if let min = g.duracionMin { detalle += "  ·  \(min) min" }
        switch g.origen {
        case "nombre": detalle += "  ·  ramo tomado del nombre del archivo"
        case "dia": detalle += "  ·  ramo tomado del día de la semana"
        default: detalle += "  ·  no reconozco el ramo"
        }
        let sub = NSTextField(labelWithString: detalle)
        sub.font = .systemFont(ofSize: 11)
        sub.textColor = .secondaryLabelColor
        sub.frame = NSRect(x: 12, y: 32, width: ancho - 24, height: 16)
        vista.addSubview(sub)

        let menu = NSPopUpButton(frame: NSRect(x: 10, y: 6, width: 320, height: 24))
        menu.addItems(withTitles: entrada.ramos)
        menu.menu?.addItem(.separator())
        menu.addItem(withTitle: OPCION_NO_ES_CLASE)
        menu.addItem(withTitle: OPCION_OTRO_RAMO)
        menu.addItem(withTitle: OPCION_OMITIR)
        menu.selectItem(withTitle: fila.seleccion)
        menu.tag = indice
        menu.target = self
        menu.action = #selector(alCambiarRamo(_:))
        vista.addSubview(menu)

        let campo = NSTextField(frame: NSRect(x: 338, y: 6, width: ancho - 350, height: 24))
        campo.placeholderString = "Nombre del ramo nuevo"
        campo.tag = 1000 + indice
        campo.isHidden = fila.seleccion != OPCION_OTRO_RAMO
        campo.delegate = self
        vista.addSubview(campo)

        if indice > 0 {
            let linea = NSBox(frame: NSRect(x: 10, y: 73, width: ancho - 20, height: 1))
            linea.boxType = .separator
            vista.addSubview(linea)
        }
        return vista
    }

    @objc private func alCambiarRamo(_ menu: NSPopUpButton) {
        guard menu.tag < filas.count, let titulo = menu.titleOfSelectedItem else { return }
        filas[menu.tag].seleccion = titulo
        // El campo de texto solo existe mientras hace falta: verlo deshabilitado
        // en todas las filas seria ruido.
        if let campo = menu.superview?.viewWithTag(1000 + menu.tag) as? NSTextField {
            campo.isHidden = titulo != OPCION_OTRO_RAMO
            if titulo == OPCION_OTRO_RAMO { ventana.makeFirstResponder(campo) }
        }
    }

    @objc private func alProcesar() {
        terminar(accion: ACCION_PROCESAR)
    }

    @objc private func alCancelar() {
        terminar(accion: "cancelar")
    }

    func windowWillClose(_ n: Notification) {
        // Cerrar la ventana no es cancelar ni aceptar: es no haber contestado.
        terminar(accion: "cerrada")
    }

    private var yaTermino = false

    private func terminar(accion: String) {
        guard !yaTermino else { return }
        yaTermino = true
        temporizador?.invalidate()
        let salida = Salida(
            accion: accion,
            decisiones: accion == ACCION_PROCESAR ? filas.map { $0.decision } : [])
        if let datos = try? JSONEncoder().encode(salida),
           let texto = String(data: datos, encoding: .utf8) {
            print(texto)
        }
        NSApp.terminate(nil)
    }
}

extension Controlador: NSTextFieldDelegate {
    func controlTextDidChange(_ n: Notification) {
        guard let campo = n.object as? NSTextField else { return }
        let indice = campo.tag - 1000
        guard indice >= 0, indice < filas.count else { return }
        filas[indice].ramoEscrito = campo.stringValue
    }
}

// MARK: - Arranque

let datosEntrada = FileHandle.standardInput.readDataToEndOfFile()
guard let entrada = try? JSONDecoder().decode(Entrada.self, from: datosEntrada),
      !entrada.grabaciones.isEmpty else {
    // Sin entrada valida no hay nada que preguntar. Salir en silencio deja que
    // Python siga con su comportamiento por defecto.
    exit(0)
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let controlador = Controlador(entrada: entrada)
app.delegate = controlador
app.run()

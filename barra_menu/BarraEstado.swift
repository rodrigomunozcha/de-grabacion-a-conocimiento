// Icono en la barra de menu de macOS que aparece solo mientras se esta
// procesando una clase, y desaparece solo al terminar.
//
// Por que existe. El flujo de la app es "suelto la clase y me voy". Sin
// ninguna senal visible, a los diez minutos no habia forma de distinguir
// entre "va bien, la skill tarda" y "se colgo hace rato", salvo abrir
// Estado.txt a mano.
//
// Por que en Swift y no en Python. Un item de barra de menu necesita
// NSStatusBar, o sea AppKit. Desde Python eso obliga a instalar PyObjC o
// rumps, dependencias grandes para un icono. Con swiftc, que ya viene con
// las herramientas de linea de comandos de Xcode, sale un binario pequeno
// sin nada que instalar en tiempo de ejecucion.
//
// Contrato con el pipeline: este programa SOLO LEE orquestador/estado_actual.json.
// No lanza nada, no escribe nada, no le habla al pipeline. Si se cae o no
// llega a abrirse, el procesamiento sigue igual. Por eso tampoco importa que
// muera de forma abrupta: no hay estado que dejar consistente.
//
// Compilar con: bash boton_app/compilar_apps.sh

import Cocoa

// MARK: - Estado que escribe el pipeline

struct Estado: Decodable {
    var activo: Bool
    var clase: String?
    var paso: Int?
    var total: Int?
    var etapa: String?
    var detalle: String?
    var inicio: Double?
    var inicioPaso: Double?
    var etaSegundos: Double?
    var error: Bool?
    var resultado: String?
    var fin: Double?
    var pid: Int?
    var interrumpible: Bool?
    var subpaso: Int?
    var subtotal: Int?
    var cancelado: Bool?
    var revertido: [String]?

    enum CodingKeys: String, CodingKey {
        case activo, clase, paso, total, etapa, detalle, inicio
        case inicioPaso = "inicio_paso"
        case etaSegundos = "eta_segundos"
        case error, resultado, fin, pid, interrumpible, cancelado, revertido
        case subpaso, subtotal
    }
}

// MARK: - Formato de tiempos

func enMinutos(_ segundos: Double) -> String {
    if segundos < 60 { return "\(Int(segundos)) s" }
    let m = Int(segundos) / 60
    let s = Int(segundos) % 60
    return s == 0 ? "\(m) min" : "\(m) min \(s) s"
}

// MARK: - Controlador

final class Controlador: NSObject, NSApplicationDelegate {
    private var item: NSStatusItem?
    private let menu = NSMenu()
    private var timer: Timer?
    private let ruta: URL

    // Al terminar se muestra el resultado unos segundos antes de cerrar, para
    // que quede algo que mirar aunque uno alcance a ver la barra justo al final.
    private var cierreProgramado: Date?
    private let segundosAntesDeCerrar: TimeInterval = 8

    init(ruta: URL) {
        self.ruta = ruta
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        // .accessory: sin icono en el Dock y sin robar el foco. El usuario
        // esta en lo suyo, esto es solo una senal.
        NSApp.setActivationPolicy(.accessory)
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.refrescar()
        }
        refrescar()
    }

    private func leerEstado() -> Estado? {
        guard let datos = try? Data(contentsOf: ruta) else { return nil }
        return try? JSONDecoder().decode(Estado.self, from: datos)
    }

    private func crearItemSiHaceFalta() {
        guard item == nil else { return }
        let nuevo = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        nuevo.menu = menu
        item = nuevo
    }

    private func refrescar() {
        guard let estado = leerEstado() else {
            // Sin archivo no hay nada que informar. Si ya habiamos mostrado
            // algo, es que la corrida termino y limpio: cerramos.
            if item != nil { NSApp.terminate(nil) }
            return
        }

        if estado.activo {
            cierreProgramado = nil
            crearItemSiHaceFalta()
            dibujarEnProgreso(estado)
        } else {
            crearItemSiHaceFalta()
            dibujarTerminado(estado)
            if cierreProgramado == nil {
                cierreProgramado = Date().addingTimeInterval(segundosAntesDeCerrar)
            } else if Date() >= cierreProgramado! {
                NSApp.terminate(nil)
            }
        }
    }

    private func dibujarEnProgreso(_ estado: Estado) {
        let paso = estado.paso ?? 0
        let total = estado.total ?? 5
        // El avance interno del paso, si lo hay: transcribir una clase larga
        // son media hora en el mismo paso, y sin esto el icono se ve tan
        // quieto como si estuviera colgado.
        var titulo = paso > 0 ? "◐ \(paso)/\(total)" : "◐"
        if let sub = estado.subpaso, let subTotal = estado.subtotal, subTotal > 1 {
            titulo += " · \(sub)/\(subTotal)"
        }
        item?.button?.title = titulo
        item?.button?.toolTip = "Procesando una clase"

        menu.removeAllItems()
        if let clase = estado.clase, !clase.isEmpty {
            agregarTitulo(clase)
        }
        agregarTitulo(paso > 0 ? "Paso \(paso) de \(total): \(estado.etapa ?? "")"
                               : (estado.etapa ?? "Preparando"))
        if let detalle = estado.detalle, !detalle.isEmpty {
            agregarLinea(detalle)
        }
        menu.addItem(.separator())

        if let inicio = estado.inicio {
            agregarLinea("Lleva \(enMinutos(Date().timeIntervalSince1970 - inicio))")
        }
        if let eta = estado.etaSegundos, let inicioPaso = estado.inicioPaso {
            let restante = eta - (Date().timeIntervalSince1970 - inicioPaso)
            agregarLinea(restante > 0
                ? "A este paso le quedan unos \(enMinutos(restante))"
                : "Este paso ya se pasó de lo habitual, sigue trabajando")
        } else {
            agregarLinea("Sin estimación para este paso")
        }

        menu.addItem(.separator())
        agregarBotonDetener(estado)
        agregarLinea("Puedes seguir usando el Mac normalmente")
    }

    // MARK: - Detener

    private func agregarBotonDetener(_ estado: Estado) {
        // Durante el movimiento del audio el boton se muestra en gris con el
        // motivo, en vez de desaparecer: que un boton se esfume sin explicacion
        // se lee como una falla, y ademas son solo unos segundos.
        let sePuede = estado.interrumpible ?? true
        let entrada = NSMenuItem(
            title: sePuede ? "Detener y deshacer todo" : "No se puede detener ahora",
            action: sePuede ? #selector(pedirDetener) : nil,
            keyEquivalent: ""
        )
        entrada.target = self
        entrada.isEnabled = sePuede
        menu.addItem(entrada)
        if !sePuede {
            agregarLinea("Se está guardando el audio, espera unos segundos")
        }
    }

    @objc private func pedirDetener() {
        guard let estado = leerEstado(), let pid = estado.pid else { return }

        let alerta = NSAlert()
        alerta.messageText = "¿Detener el procesamiento?"
        alerta.informativeText = """
        Se deshará todo lo que se haya hecho hasta ahora: las notas que se \
        alcanzaron a escribir, el documento generado y las flashcards agregadas. \
        Tu grabación vuelve a donde estaba, sin procesar.

        Es como si nunca hubieras hecho clic.
        """
        alerta.alertStyle = .warning
        alerta.addButton(withTitle: "Detener y deshacer")
        alerta.addButton(withTitle: "Seguir procesando")

        NSApp.activate(ignoringOtherApps: true)
        guard alerta.runModal() == .alertFirstButtonReturn else { return }

        // SIGTERM y no SIGKILL: el pipeline lo atiende, deshace lo anotado y
        // sale ordenado. Matarlo en seco dejaria justamente el desorden que
        // este boton existe para evitar (ver cancelacion.py).
        kill(pid_t(pid), SIGTERM)
        item?.button?.title = "◌"
    }

    private func dibujarTerminado(_ estado: Estado) {
        let huboError = estado.error ?? false
        let seCancelo = estado.cancelado ?? false
        item?.button?.title = seCancelo ? "◌" : (huboError ? "✕" : "✓")
        menu.removeAllItems()
        agregarTitulo(seCancelo ? "Detenido, todo quedó como estaba"
                                : (huboError ? "Terminó con un problema" : "Clase procesada"))
        if let resultado = estado.resultado, !resultado.isEmpty, !seCancelo {
            agregarLinea(resultado)
        }
        // Se lista lo que se revirtio, para no tener que confiar en la palabra
        // del programa: el estudiante ve exactamente que se deshizo.
        if seCancelo, let revertido = estado.revertido, !revertido.isEmpty {
            for linea in revertido.prefix(8) { agregarLinea(linea) }
        }
        if let inicio = estado.inicio {
            agregarLinea("Tardó \(enMinutos((estado.fin ?? Date().timeIntervalSince1970) - inicio))")
        }
        if huboError {
            menu.addItem(.separator())
            agregarLinea("El detalle quedó en orquestador/logs/errores.log")
        }
    }

    private func agregarTitulo(_ texto: String) {
        let entrada = NSMenuItem(title: texto, action: nil, keyEquivalent: "")
        entrada.attributedTitle = NSAttributedString(
            string: texto,
            attributes: [.font: NSFont.boldSystemFont(ofSize: 13)]
        )
        menu.addItem(entrada)
    }

    private func agregarLinea(_ texto: String) {
        let entrada = NSMenuItem(title: texto, action: nil, keyEquivalent: "")
        entrada.attributedTitle = NSAttributedString(
            string: texto,
            attributes: [.font: NSFont.systemFont(ofSize: 12),
                         .foregroundColor: NSColor.secondaryLabelColor]
        )
        menu.addItem(entrada)
    }
}

// MARK: - Arranque

let argumentos = CommandLine.arguments
guard argumentos.count > 1 else {
    FileHandle.standardError.write("Uso: BarraEstado <ruta a estado_actual.json>\n".data(using: .utf8)!)
    exit(1)
}

let app = NSApplication.shared
let controlador = Controlador(ruta: URL(fileURLWithPath: argumentos[1]))
app.delegate = controlador
app.run()

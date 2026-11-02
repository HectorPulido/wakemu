import AppKit
import WebKit

// The desktop shell never handles game packets or injects scripts into the portal.
final class LauncherFormDocument: NSView { override var isFlipped: Bool { true } }

final class Launcher: NSObject, NSApplicationDelegate, NSWindowDelegate, NSTextFieldDelegate, NSComboBoxDelegate, WKNavigationDelegate, WKUIDelegate, NSTabViewDelegate {
    var window: NSWindow!
    var tabs = NSTabView()
    let serverPicker = NSPopUpButton()
    let username = NSComboBox()
    let password = NSSecureTextField()
    let remember = NSButton(checkboxWithTitle: "Guardar cuenta y contraseña", target: nil, action: nil)
    let status = NSTextField(wrappingLabelWithString: "Cargando tus servidores…")
    let webStatus = NSTextField(wrappingLabelWithString: "Usa la cuenta seleccionada en Jugar para consultar logros y teletransportarte.")
    let address = NSTextField()
    var webView: WKWebView!
    var fields: [String: NSTextField] = [:]
    var servers: [[String: Any]] = []
    var currentID = "internet"
    var loading = false
    var busy = false
    var passwordEdited = false
    var knownUsername = ""
    var saveTimer: Timer?
    var pendingSave = false
    var closeAfterSave = false
    var loadedPortal: String?
    var webStack: NSStackView!
    var identityGeneration = 0
    var pendingPortal = false
    var pendingAccountRestore = false
    var registrationPanel: NSPanel?
    var registrationServer: [String: Any] = [:]
    var registrationUsername = NSTextField()
    var registrationPassword = NSSecureTextField()
    var registrationConfirm = NSSecureTextField()
    var registrationStatus = NSTextField(wrappingLabelWithString: "")
    var registrationCreate = NSButton()
    var registrationCancel = NSButton()
    var controls: [NSControl] = []
    var advancedStack = NSStackView()
    var advancedToggle = NSButton()
    var pendingDiscovery = false
    var discoveryGeneration = 0
    var committedDomain = ""
    var domainPasswordBackup: (domain: String, password: String, edited: Bool)?
    let root: URL
    let smoke: Bool
    #if LAUNCHER_QA
    let webSmoke = CommandLine.arguments.contains("--web-smoke")
    let registrationSmoke = CommandLine.arguments.contains("--registration-smoke")
    var registrationChecks: [String: Bool] = [:]
    var registrationHeartbeat = 0
    var registrationUnexpectedRequests = 0
    var registrationHeartbeatTimer: Timer?
    #else
    let webSmoke = false
    #endif
    var webSmokeAttempts = 0
    var webSmokeScheduled = false

    override init() {
        #if LAUNCHER_QA
        smoke = CommandLine.arguments.contains("--ui-smoke") || CommandLine.arguments.contains("--registration-smoke")
        #else
        smoke = false
        #endif
        if let configured = ProcessInfo.processInfo.environment["WAKFU_LAUNCHER_ROOT"] {
            root = URL(fileURLWithPath: configured, isDirectory: true)
        } else {
            root = Bundle.main.bundleURL.deletingLastPathComponent()
        }
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.appearance = NSAppearance(named: .aqua)
        buildUI()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        if smoke {
            applyState(["servers": [["id": "internet", "name": "Wakemu Internet", "server_host": "wakemu.p.hectorpulido.net", "dispatch_port": 15558, "game_ports": [15556], "chat_host": "wakemu.p.hectorpulido.net", "chat_port": 16337, "api_url": "https://wakemu.p.hectorpulido.net", "http_url": "https://wakemu.p.hectorpulido.net", "shop_url": "https://wakemu.p.hectorpulido.net", "achievements_url": "https://wakemu.p.hectorpulido.net", "certificate": "", "install_root": ""]], "selected_id": "internet", "username": "", "accounts": [], "remember": true])
            status.stringValue = "Interfaz de prueba; no se inicia sesión ni se abre el juego."
            #if LAUNCHER_QA
            if registrationSmoke {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { self.startRegistrationAcceptance() }
            } else {
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.saveSnapshotAndExit() }
            }
            #endif
        } else {
            request("state", [:]) { result in
                if let state = result["state"] as? [String: Any] { self.applyState(state) }
                if self.webSmoke { self.startWebAcceptance() }
                else { self.detectConfiguration() }
            }
        }
    }

    func label(_ text: String) -> NSTextField {
        let view = NSTextField(labelWithString: text)
        view.font = .systemFont(ofSize: 13)
        view.textColor = NSColor(srgbRed: 0.09, green: 0.18, blue: 0.23, alpha: 1)
        return view
    }

    func button(_ title: String, _ action: Selector) -> NSButton {
        let control = NSButton(title: title, target: self, action: action)
        control.bezelStyle = .rounded
        controls.append(control)
        return control
    }

    func row(_ key: String, _ title: String, browse: Selector? = nil) -> NSView {
        let input = NSTextField()
        input.delegate = self
        input.identifier = NSUserInterfaceItemIdentifier(key)
        input.placeholderString = title
        fields[key] = input
        input.widthAnchor.constraint(greaterThanOrEqualToConstant: 420).isActive = true
        let caption = label(title)
        caption.widthAnchor.constraint(equalToConstant: 205).isActive = true
        let stack = NSStackView(views: [caption, input])
        stack.orientation = .horizontal
        stack.spacing = 12
        stack.alignment = .centerY
        input.setContentHuggingPriority(.defaultLow, for: .horizontal)
        if let browse = browse { stack.addArrangedSubview(button("Elegir…", browse)) }
        return stack
    }

    func buildUI() {
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1060, height: 650), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Wakfu · Minilauncher"
        window.appearance = NSAppearance(named: .aqua)
        window.minSize = NSSize(width: 900, height: 580)
        window.center()
        window.delegate = self
        window.isReleasedWhenClosed = false
        window.contentView!.wantsLayer = true
        // A layer stores a resolved CGColor; semantic colors can resolve using the
        // system's dark appearance before the view inherits the window appearance.
        window.contentView!.layer?.backgroundColor = NSColor(srgbRed: 0.96, green: 0.97, blue: 0.98, alpha: 1).cgColor
        let outer = NSStackView()
        outer.orientation = .vertical
        outer.spacing = 14
        outer.alignment = .leading
        outer.translatesAutoresizingMaskIntoConstraints = false
        window.contentView!.addSubview(outer)
        NSLayoutConstraint.activate([
            outer.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor, constant: 22),
            outer.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor, constant: -22),
            outer.topAnchor.constraint(equalTo: window.contentView!.topAnchor, constant: 18),
            outer.bottomAnchor.constraint(equalTo: window.contentView!.bottomAnchor, constant: -18)
        ])
        let title = label("WAKFU")
        title.font = .systemFont(ofSize: 30, weight: .semibold)
        let version = label("1.93.1+79  ·  Tu servidor. Tus cuentas.")
        version.textColor = NSColor(srgbRed: 0.30, green: 0.36, blue: 0.39, alpha: 1)
        let header = NSStackView(views: [title, version])
        header.spacing = 24
        header.alignment = .centerY
        outer.addArrangedSubview(header)
        let navigation = NSStackView(views: [button("Jugar", #selector(selectPlayTab)), button("Logros y mazmorras", #selector(selectPortalTab))])
        navigation.orientation = .horizontal
        navigation.spacing = 12
        outer.addArrangedSubview(navigation)
        tabs.tabViewType = .noTabsNoBorder
        tabs.appearance = NSAppearance(named: .aqua)
        tabs.delegate = self
        tabs.translatesAutoresizingMaskIntoConstraints = false
        outer.addArrangedSubview(tabs)
        tabs.widthAnchor.constraint(equalTo: outer.widthAnchor).isActive = true
        let playTab = NSTabViewItem(identifier: "play")
        playTab.label = "Jugar"
        let page = NSView()
        playTab.view = page
        tabs.addTabViewItem(playTab)
        let scroll = NSScrollView()
        scroll.hasVerticalScroller = true
        scroll.drawsBackground = false
        scroll.translatesAutoresizingMaskIntoConstraints = false
        page.addSubview(scroll)
        NSLayoutConstraint.activate([
            scroll.leadingAnchor.constraint(equalTo: page.leadingAnchor),
            scroll.trailingAnchor.constraint(equalTo: page.trailingAnchor),
            scroll.topAnchor.constraint(equalTo: page.topAnchor),
            scroll.bottomAnchor.constraint(equalTo: page.bottomAnchor)
        ])
        let document = LauncherFormDocument()
        document.translatesAutoresizingMaskIntoConstraints = false
        scroll.documentView = document
        document.widthAnchor.constraint(equalTo: scroll.contentView.widthAnchor).isActive = true
        let stack = NSStackView()
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 11
        stack.translatesAutoresizingMaskIntoConstraints = false
        document.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: document.leadingAnchor, constant: 18),
            stack.trailingAnchor.constraint(equalTo: document.trailingAnchor, constant: -18),
            stack.topAnchor.constraint(equalTo: document.topAnchor, constant: 18),
            stack.bottomAnchor.constraint(equalTo: document.bottomAnchor, constant: -18)
        ])
        serverPicker.target = self
        serverPicker.action = #selector(serverChanged)
        serverPicker.widthAnchor.constraint(greaterThanOrEqualToConstant: 420).isActive = true
        controls.append(serverPicker)
        let serverRow = NSStackView(views: [serverPicker, button("Nuevo servidor", #selector(newServer))])
        serverRow.spacing = 14
        stack.addArrangedSubview(serverRow)
        stack.addArrangedSubview(row("name", "Nombre del servidor"))
        stack.addArrangedSubview(row("server_host", "Dominio o IP del servidor"))
        fields["server_host"]?.placeholderString = "wakemu.p.hectorpulido.net"
        stack.addArrangedSubview(button("Detectar configuración", #selector(detectConfiguration)))
        username.delegate = self
        username.usesDataSource = false
        username.completes = false
        username.identifier = NSUserInterfaceItemIdentifier("username")
        username.widthAnchor.constraint(equalToConstant: 300).isActive = true
        password.delegate = self
        password.identifier = NSUserInterfaceItemIdentifier("password")
        password.widthAnchor.constraint(equalToConstant: 300).isActive = true
        let accountRow = NSStackView(views: [label("Usuario"), username, label("Contraseña"), password])
        accountRow.spacing = 10
        stack.addArrangedSubview(accountRow)
        remember.state = .on
        remember.target = self
        remember.action = #selector(rememberChanged)
        stack.addArrangedSubview(remember)
        let buttons = NSStackView(views: [button("Olvidar acceso", #selector(forget)), button("Registrarse", #selector(showRegistration)), button("Comprobar conexión", #selector(check)), button("Jugar", #selector(play))])
        buttons.spacing = 14
        stack.addArrangedSubview(buttons)
        status.textColor = NSColor(srgbRed: 0.30, green: 0.36, blue: 0.39, alpha: 1)
        status.maximumNumberOfLines = 3
        stack.addArrangedSubview(status)
        status.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        advancedToggle = NSButton(checkboxWithTitle: "Configuración avanzada", target: self, action: #selector(toggleAdvanced))
        controls.append(advancedToggle)
        stack.addArrangedSubview(advancedToggle)
        advancedStack.orientation = .vertical
        advancedStack.alignment = .leading
        advancedStack.spacing = 11
        for (key, title) in [
            ("dispatch_port", "Puerto de conexión"), ("game_ports", "Puertos del mundo"),
            ("chat_host", "IP o dominio del chat"), ("chat_port", "Puerto del chat"),
            ("api_url", "Autenticación (URL)"), ("http_url", "Recursos del juego (URL)"),
            ("shop_url", "Tienda (URL)"), ("achievements_url", "Logros y mazmorras (URL)")
        ] { advancedStack.addArrangedSubview(row(key, title)) }
        advancedStack.addArrangedSubview(row("certificate", "Certificado (opcional)", browse: #selector(browseCertificate)))
        advancedStack.addArrangedSubview(row("install_root", "Carpeta del cliente", browse: #selector(browseClient)))
        stack.addArrangedSubview(advancedStack)
        advancedStack.isHidden = true
        buildPortal()
    }

    func buildPortal() {
        let tab = NSTabViewItem(identifier: "portal")
        tab.label = "Logros y mazmorras"
        let view = NSView()
        tab.view = view
        tabs.addTabViewItem(tab)
        let stack = NSStackView()
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 10
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 12),
            stack.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -12),
            stack.topAnchor.constraint(equalTo: view.topAnchor, constant: 12),
            stack.bottomAnchor.constraint(equalTo: view.bottomAnchor, constant: -12)
        ])
        address.isEditable = false
        address.isSelectable = true
        address.isBezeled = false
        address.drawsBackground = false
        address.setContentHuggingPriority(.defaultLow, for: .horizontal)
        let toolbar = NSStackView(views: [address, button("Inicio", #selector(portalHome)), button("Recargar", #selector(reloadPortal))])
        toolbar.spacing = 10
        stack.addArrangedSubview(toolbar)
        toolbar.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        webStatus.textColor = NSColor(srgbRed: 0.30, green: 0.36, blue: 0.39, alpha: 1)
        webStatus.font = .systemFont(ofSize: 12)
        stack.addArrangedSubview(webStatus)
        webStatus.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        webStack = stack
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()
        webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        stack.addArrangedSubview(webView)
        webView.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        webView.heightAnchor.constraint(greaterThanOrEqualToConstant: 420).isActive = true
    }

    func selectedPortal() -> String { fields["achievements_url"]?.stringValue.trimmingCharacters(in: .whitespacesAndNewlines) ?? "" }

    func clearPortal() {
        identityGeneration += 1
        loadedPortal = nil
        guard webView != nil, webStack != nil else { return }
        webView.stopLoading()
        webView.navigationDelegate = nil
        webView.uiDelegate = nil
        webStack.removeArrangedSubview(webView)
        webView.removeFromSuperview()
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()
        webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webStack.addArrangedSubview(webView)
        webView.widthAnchor.constraint(equalTo: webStack.widthAnchor).isActive = true
        webView.heightAnchor.constraint(greaterThanOrEqualToConstant: 420).isActive = true
        address.stringValue = selectedPortal()
        webStatus.stringValue = "La página se abrirá con la cuenta seleccionada en Jugar."
    }

    @objc func portalHome() {
        if smoke { return }
        guard !busy else { pendingPortal = true; return }
        let candidate = selectedPortal()
        guard let url = URL(string: candidate), ["https", "http"].contains(url.scheme ?? ""), url.host != nil, url.user == nil, url.password == nil else {
            webStatus.stringValue = "Indica la URL de la página de logros en la pestaña Jugar."
            return
        }
        saveTimer?.invalidate()
        let generation = identityGeneration
        webStatus.stringValue = "Abriendo logros y mazmorras con tu cuenta…"
        request("web-login", payload()) { response in
            guard self.identityGeneration == generation,
                  let target = response["url"] as? String,
                  let destination = URL(string: target),
                  ["http", "https"].contains(destination.scheme ?? ""),
                  destination.host == url.host,
                  destination.port == url.port,
                  destination.scheme == url.scheme else { return }
            self.loadedPortal = candidate
            self.address.stringValue = candidate
            self.webView.load(URLRequest(url: destination))
        }
    }

    @objc func reloadPortal() {
        if loadedPortal != selectedPortal() { portalHome() } else { webView.reload() }
    }

    @objc func selectPlayTab() { tabs.selectTabViewItem(at: 0) }
    @objc func selectPortalTab() { tabs.selectTabViewItem(at: 1) }

    func tabView(_ tabView: NSTabView, didSelect tabViewItem: NSTabViewItem?) {
        if tabViewItem?.identifier as? String == "portal" && loadedPortal != selectedPortal() { portalHome() }
    }

    func portalOriginAllows(_ url: URL) -> Bool {
        if url.absoluteString == "about:blank" { return true }
        guard let home = URL(string: selectedPortal()) else { return false }
        return ["http", "https"].contains(url.scheme ?? "") && url.scheme == home.scheme && url.host == home.host && url.port == home.port
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url, portalOriginAllows(url) else {
            webStatus.stringValue = "El enlace sale de la página de logros configurada y no se abrió."
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url, portalOriginAllows(url) { webView.load(URLRequest(url: url)) }
        return nil
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        if let url = webView.url, var shown = URLComponents(url: url, resolvingAgainstBaseURL: false) {
            shown.fragment = nil
            shown.query = nil
            address.stringValue = shown.string ?? selectedPortal()
        }
        webStatus.stringValue = "Cuenta: \(username.stringValue). Verifica el personaje antes de usar un teletransporte."
        if webSmoke && !webSmokeScheduled { webSmokeScheduled = true; DispatchQueue.main.asyncAfter(deadline: .now() + 2) { self.inspectWebAcceptance() } }
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        webStatus.stringValue = "No se pudo cargar la página. Revisa su URL y la conexión."
    }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert = NSAlert()
        alert.messageText = message
        alert.beginSheetModal(for: window) { _ in completionHandler() }
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = NSAlert()
        alert.messageText = message
        alert.addButton(withTitle: "Aceptar")
        alert.addButton(withTitle: "Cancelar")
        alert.beginSheetModal(for: window) { response in completionHandler(response == .alertFirstButtonReturn) }
    }

    func applyState(_ state: [String: Any]) {
        loading = true
        defer { loading = false }
        let incomingServers = state["servers"] as? [[String: Any]] ?? []
        let incomingID = state["selected_id"] as? String ?? incomingServers.first?["id"] as? String ?? "internet"
        let incomingUsername = state["username"] as? String ?? state["selected_username"] as? String ?? ""
        let incomingServer = incomingServers.first(where: { $0["id"] as? String == incomingID }) ?? [:]
        let endpointChanged = fields.contains { key, field in
            guard !["name", "install_root"].contains(key) else { return false }
            let value: String
            if key == "game_ports", let ports = incomingServer[key] as? [Int] { value = ports.map(String.init).joined(separator: ",") }
            else { value = incomingServer[key].map { String(describing: $0) } ?? "" }
            return value != field.stringValue
        }
        if incomingID != currentID || incomingUsername != knownUsername || endpointChanged { clearPortal() }
        servers = incomingServers
        discoveryGeneration += 1
        currentID = state["selected_id"] as? String ?? servers.first?["id"] as? String ?? "internet"
        serverPicker.removeAllItems()
        for server in servers { serverPicker.addItem(withTitle: server["name"] as? String ?? "Servidor") }
        if let index = servers.firstIndex(where: { $0["id"] as? String == currentID }) { serverPicker.selectItem(at: index) }
        let server = servers.first(where: { $0["id"] as? String == currentID }) ?? [:]
        for (key, field) in fields {
            if key == "game_ports", let values = server[key] as? [Int] { field.stringValue = values.map(String.init).joined(separator: ",") }
            else if let value = server[key] { field.stringValue = String(describing: value) }
            else { field.stringValue = "" }
        }
        domainPasswordBackup = nil
        committedDomain = normalizedDomain(fields["server_host"]?.stringValue ?? "")
        username.removeAllItems()
        username.addItems(withObjectValues: state["accounts"] as? [String] ?? [])
        username.stringValue = state["username"] as? String ?? state["selected_username"] as? String ?? ""
        knownUsername = username.stringValue
        password.stringValue = state["password"] as? String ?? ""
        remember.state = state["remember"] as? Bool == false ? .off : .on
        passwordEdited = false
        status.stringValue = "Los cambios se guardan automáticamente."
    }

    func payload() -> [String: Any] {
        var server: [String: Any] = ["id": currentID]
        for (key, field) in fields { server[key] = field.stringValue }
        // Backend validation accepts port strings and a comma-separated game-port list.
        return ["server": server, "username": username.stringValue, "password": password.stringValue, "remember": remember.state == .on, "password_edited": passwordEdited]
    }

    func pythonCommand() -> (URL, [String]) {
        for candidate in [root.appendingPathComponent("python/bin/python3"), root.appendingPathComponent("python/bin/python3.13")] {
            if FileManager.default.isExecutableFile(atPath: candidate.path) { return (candidate, []) }
        }
        return (URL(fileURLWithPath: "/usr/bin/env"), ["python3"])
    }

    func request(_ action: String, _ data: [String: Any], onFailure: (([String: Any]) -> Void)? = nil, completion: @escaping ([String: Any]) -> Void = { _ in }) {
        #if LAUNCHER_QA
        if registrationSmoke { registrationUnexpectedRequests += 1; return }
        #endif
        guard !busy else { if action == "save" { pendingSave = true }; return }
        busy = true
        let (executable, arguments) = pythonCommand()
        let inputData: Data
        do { inputData = try JSONSerialization.data(withJSONObject: data) }
        catch { busy = false; status.stringValue = "No se pudo preparar la configuración."; return }
        status.stringValue = action == "discover" ? "Detectando puertos y servicios…" : action == "register" ? "Creando la cuenta…" : action == "play" ? "Autenticando y abriendo Wakfu…" : action == "check" ? "Comprobando conexión…" : "Guardando…"
        for control in controls { control.isEnabled = false }
        DispatchQueue.global(qos: .userInitiated).async {
            let process = Process()
            process.executableURL = executable
            process.arguments = arguments + ["-B", self.root.appendingPathComponent("mini-launcher/launcher_backend.py").path, "--action", action]
            process.currentDirectoryURL = self.root
            var environment = ProcessInfo.processInfo.environment
            environment["PYTHONIOENCODING"] = "utf-8"
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            process.environment = environment
            let input = Pipe(), output = Pipe(), errors = Pipe()
            process.standardInput = input
            process.standardOutput = output
            process.standardError = errors
            var result: [String: Any] = ["ok": false, "error": "No se pudo iniciar el launcher. Comprueba Python y la carpeta del paquete."]
            do {
                try process.run()
                input.fileHandleForWriting.write(inputData)
                try input.fileHandleForWriting.close()
                // Errors are drained concurrently so neither pipe can block the backend.
                let group = DispatchGroup()
                group.enter()
                DispatchQueue.global().async { _ = errors.fileHandleForReading.readDataToEndOfFile(); group.leave() }
                let raw = output.fileHandleForReading.readDataToEndOfFile()
                process.waitUntilExit()
                group.wait()
                if let decoded = try JSONSerialization.jsonObject(with: raw) as? [String: Any] { result = decoded }
            } catch { }
            let response = result
            DispatchQueue.main.async {
                self.busy = false
                for control in self.controls { control.isEnabled = true }
                if response["ok"] as? Bool != true {
                    self.status.stringValue = response["error"] as? String ?? "No se pudo completar la operación."
                    if action == "web-login" { self.webStatus.stringValue = self.status.stringValue }
                    onFailure?(response)
                } else {
                    self.status.stringValue = response["message"] as? String ?? "Cambios guardados."
                    if action == "save", let state = response["state"] as? [String: Any], let savedServers = state["servers"] as? [[String: Any]] {
                        self.loading = true
                        self.servers = savedServers
                        self.serverPicker.removeAllItems()
                        for server in savedServers { self.serverPicker.addItem(withTitle: server["name"] as? String ?? "Servidor") }
                        if let index = savedServers.firstIndex(where: { $0["id"] as? String == self.currentID }) { self.serverPicker.selectItem(at: index) }
                        self.loading = false
                    }
                    completion(response)
                }
                if self.closeAfterSave {
                    self.closeAfterSave = false
                    if response["ok"] as? Bool == true { NSApp.terminate(nil); return }
                }
                if self.pendingDiscovery { self.pendingDiscovery = false; self.detectConfiguration() }
                else if self.pendingAccountRestore { self.pendingAccountRestore = false; self.restoreAccount() }
                else if self.pendingPortal { self.pendingPortal = false; self.portalHome() }
                else if self.pendingSave { self.pendingSave = false; self.scheduleSave() }
            }
        }
    }

    func scheduleSave() {
        if loading || smoke { return }
        saveTimer?.invalidate()
        saveTimer = Timer.scheduledTimer(withTimeInterval: 0.8, repeats: false) { _ in
            let data = self.payload()
            self.request("save", data)
        }
    }

    func controlTextDidChange(_ obj: Notification) {
        guard !loading else { return }
        if let control = obj.object as? NSControl {
            if control.identifier?.rawValue == "server_host" {
                discoveryGeneration += 1
                if normalizedDomain(fields["server_host"]?.stringValue ?? "") != committedDomain {
                    if domainPasswordBackup == nil { domainPasswordBackup = (committedDomain, password.stringValue, passwordEdited) }
                    clearPortal()
                    password.stringValue = ""
                    passwordEdited = false
                }
                saveTimer?.invalidate()
                return
            }
            if control === password { passwordEdited = true; domainPasswordBackup = nil }
            else if control === username {
                if username.stringValue != knownUsername {
                    domainPasswordBackup = nil
                    clearPortal()
                    password.stringValue = ""
                    passwordEdited = false
                    knownUsername = username.stringValue
                }
            } else if let key = control.identifier?.rawValue, !["name", "install_root"].contains(key) {
                clearPortal()
                password.stringValue = ""
                passwordEdited = false
            }
        }
        scheduleSave()
    }

    func controlTextDidEndEditing(_ obj: Notification) {
        guard !loading, let control = obj.object as? NSControl else { return }
        if control.identifier?.rawValue == "server_host" { detectConfiguration(); return }
        if control === username && !passwordEdited { restoreAccount() }
    }

    func comboBoxSelectionDidChange(_ notification: Notification) {
        guard !loading else { return }
        if username.indexOfSelectedItem >= 0 { username.stringValue = username.itemObjectValue(at: username.indexOfSelectedItem) as? String ?? "" }
        domainPasswordBackup = nil
        clearPortal()
        password.stringValue = ""
        passwordEdited = false
        knownUsername = username.stringValue
        restoreAccount()
    }

    func restoreAccount() {
        if busy { pendingAccountRestore = true; return }
        saveTimer?.invalidate()
        let serverID = currentID, account = username.stringValue
        request("state", ["selected_id": serverID, "username": account]) { response in
            guard self.currentID == serverID, self.username.stringValue == account, !self.passwordEdited, let state = response["state"] as? [String: Any] else { return }
            self.loading = true
            self.password.stringValue = state["password"] as? String ?? ""
            self.remember.state = state["remember"] as? Bool == false ? .off : .on
            self.loading = false
            self.scheduleSave()
        }
    }

    @objc func toggleAdvanced() {
        advancedStack.isHidden = advancedToggle.state != .on
    }

    func normalizedDomain(_ value: String) -> String {
        var result = value.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if result.hasPrefix("https://") { result.removeFirst(8) }
        else if result.hasPrefix("http://") { result.removeFirst(7) }
        while result.hasSuffix("/") { result.removeLast() }
        return result
    }

    @objc func detectConfiguration() {
        if smoke { return }
        if busy { pendingDiscovery = true; return }
        saveTimer?.invalidate()
        let domain = normalizedDomain(fields["server_host"]?.stringValue ?? "")
        guard !domain.isEmpty else { status.stringValue = "Escribe el dominio o la IP de tu servidor."; return }
        loading = true
        fields["server_host"]?.stringValue = domain
        if let backup = domainPasswordBackup, domain == backup.domain, password.stringValue.isEmpty, !passwordEdited {
            password.stringValue = backup.password
            passwordEdited = backup.edited
        }
        domainPasswordBackup = nil
        if domain != committedDomain {
            // A new host must never inherit another server's authentication URL.
            clearPortal()
            password.stringValue = ""
            passwordEdited = false
            for key in ["api_url", "http_url", "shop_url", "achievements_url"] { fields[key]?.stringValue = "https://" + domain }
            fields["chat_host"]?.stringValue = domain
            fields["certificate"]?.stringValue = ""
        }
        loading = false
        let generation = discoveryGeneration
        let serverID = currentID
        let server = payload()["server"] as? [String: Any] ?? [:]
        // Discovery receives server configuration only, never account credentials.
        request("discover", ["server": server], onFailure: { response in
            guard self.currentID == serverID, self.discoveryGeneration == generation,
                  self.normalizedDomain(self.fields["server_host"]?.stringValue ?? "") == domain else { return }
            self.status.stringValue = response["error"] as? String ?? "No se pudo detectar la configuración. Revisa el dominio o abre Configuración avanzada."
        }) { response in
            guard self.currentID == serverID, self.discoveryGeneration == generation,
                  self.normalizedDomain(self.fields["server_host"]?.stringValue ?? "") == domain,
                  let discovered = response["server"] as? [String: Any] else { return }
            self.loading = true
            var changed = false
            for (key, field) in self.fields {
                if key == "name" || key == "install_root" { continue }
                guard let value = discovered[key] else { continue }
                let text: String
                if key == "game_ports", let ports = value as? [Int] { text = ports.map(String.init).joined(separator: ",") }
                else { text = String(describing: value) }
                if text != field.stringValue { changed = true }
                field.stringValue = text
            }
            if changed { self.clearPortal() }
            self.committedDomain = self.normalizedDomain(self.fields["server_host"]?.stringValue ?? domain)
            self.loading = false
            self.status.stringValue = response["message"] as? String ?? "Puertos y servicios detectados automáticamente."
            self.scheduleSave()
        }
    }

    @objc func rememberChanged() { scheduleSave() }

    @objc func serverChanged() {
        saveTimer?.invalidate()
        let index = serverPicker.indexOfSelectedItem
        guard servers.indices.contains(index), let nextID = servers[index]["id"] as? String, nextID != currentID else { return }
        clearPortal()
        let oldData = payload()
        request("save", oldData) { _ in
            self.request("state", ["selected_id": nextID]) { response in
                if let state = response["state"] as? [String: Any] { self.applyState(state); self.detectConfiguration() }
            }
        }
    }

    @objc func newServer() {
        saveTimer?.invalidate()
        clearPortal()
        let oldData = payload()
        request("save", oldData) { _ in
            self.loading = true
            self.currentID = UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
            self.fields["name"]?.stringValue = "Nuevo servidor"
            self.domainPasswordBackup = nil
            self.username.stringValue = ""
            self.password.stringValue = ""
            self.knownUsername = ""
            self.passwordEdited = false
            self.remember.state = .on
            self.loading = false
            self.discoveryGeneration += 1
            self.detectConfiguration()
        }
    }

    @objc func forget() {
        clearPortal()
        saveTimer?.invalidate()
        request("forget", ["selected_id": currentID, "username": username.stringValue]) { response in
            if let state = response["state"] as? [String: Any] { self.applyState(state) }
        }
    }
    @objc func check() { saveTimer?.invalidate(); request("check", payload()) }
    @objc func play() { saveTimer?.invalidate(); request("play", payload()) }

    @objc func showRegistration() {
        guard !busy, registrationPanel == nil else { return }
        saveTimer?.invalidate()
        registrationServer = payload()["server"] as? [String: Any] ?? [:]
        let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 510, height: 290), styleMask: [.titled], backing: .buffered, defer: false)
        panel.title = "Crear una cuenta"
        panel.appearance = NSAppearance(named: .aqua)
        panel.isReleasedWhenClosed = false
        let stack = NSStackView()
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false
        panel.contentView!.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: panel.contentView!.leadingAnchor, constant: 22),
            stack.trailingAnchor.constraint(equalTo: panel.contentView!.trailingAnchor, constant: -22),
            stack.topAnchor.constraint(equalTo: panel.contentView!.topAnchor, constant: 20)
        ])
        let explanation = NSTextField(wrappingLabelWithString: "Crea una cuenta en el servidor seleccionado. Después podrás iniciar el juego con ella.")
        explanation.textColor = NSColor(srgbRed: 0.20, green: 0.26, blue: 0.29, alpha: 1)
        stack.addArrangedSubview(explanation)
        explanation.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        registrationUsername = NSTextField()
        registrationPassword = NSSecureTextField()
        registrationConfirm = NSSecureTextField()
        for (caption, field) in [("Nuevo usuario", registrationUsername), ("Contraseña", registrationPassword), ("Repetir contraseña", registrationConfirm)] {
            let captionView = label(caption)
            captionView.widthAnchor.constraint(equalToConstant: 150).isActive = true
            field.widthAnchor.constraint(equalToConstant: 290).isActive = true
            let row = NSStackView(views: [captionView, field])
            row.spacing = 12
            stack.addArrangedSubview(row)
        }
        registrationStatus = NSTextField(wrappingLabelWithString: "La cuenta actual se conservará si cancelas.")
        registrationStatus.textColor = NSColor(srgbRed: 0.30, green: 0.36, blue: 0.39, alpha: 1)
        registrationStatus.maximumNumberOfLines = 2
        stack.addArrangedSubview(registrationStatus)
        registrationStatus.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        registrationCreate = NSButton(title: "Crear cuenta", target: self, action: #selector(submitRegistration))
        registrationCreate.bezelStyle = .rounded
        registrationCreate.keyEquivalent = "\r"
        registrationCancel = NSButton(title: "Cancelar", target: self, action: #selector(cancelRegistration))
        registrationCancel.bezelStyle = .rounded
        registrationCancel.keyEquivalent = "\u{1b}"
        let actions = NSStackView(views: [registrationCancel, registrationCreate])
        actions.spacing = 14
        stack.addArrangedSubview(actions)
        registrationPanel = panel
        window.beginSheet(panel)
        panel.makeFirstResponder(registrationUsername)
    }

    @objc func cancelRegistration() {
        guard !busy else { return }
        dismissRegistration()
        scheduleSave()
    }

    func dismissRegistration() {
        guard let panel = registrationPanel else { return }
        window.endSheet(panel)
        panel.orderOut(nil)
        registrationPanel = nil
        registrationServer = [:]
        registrationUsername.stringValue = ""
        registrationPassword.stringValue = ""
        registrationConfirm.stringValue = ""
    }

    @objc func submitRegistration() {
        guard !busy, registrationPanel != nil else { return }
        let account = registrationUsername.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !account.isEmpty, !registrationPassword.stringValue.isEmpty else {
            registrationStatus.stringValue = "Escribe un nuevo usuario y una contraseña."
            return
        }
        guard registrationPassword.stringValue == registrationConfirm.stringValue else {
            registrationStatus.stringValue = "Las contraseñas no coinciden."
            registrationPanel?.makeFirstResponder(registrationConfirm)
            return
        }
        let data: [String: Any] = ["server": registrationServer, "username": account,
                                   "password": registrationPassword.stringValue,
                                   "password_confirm": registrationConfirm.stringValue,
                                   "remember": remember.state == .on]
        registrationCreate.isEnabled = false
        registrationCancel.isEnabled = false
        for field in [registrationUsername, registrationPassword, registrationConfirm] { field.isEnabled = false }
        registrationStatus.stringValue = "Creando la cuenta…"
        request("register", data, onFailure: { response in
            self.registrationCreate.isEnabled = true
            self.registrationCancel.isEnabled = true
            for field in [self.registrationUsername, self.registrationPassword, self.registrationConfirm] { field.isEnabled = true }
            self.registrationStatus.stringValue = response["error"] as? String ?? "No se pudo crear la cuenta."
        }) { response in
            self.dismissRegistration()
            self.clearPortal()
            if let state = response["state"] as? [String: Any] { self.applyState(state) }
            self.status.stringValue = response["message"] as? String ?? "Cuenta creada. Ya puedes iniciar el juego."
        }
    }

    @objc func browseCertificate() { browse(key: "certificate", directory: false) }
    @objc func browseClient() { browse(key: "install_root", directory: true) }
    func browse(key: String, directory: Bool) {
        let dialog = NSOpenPanel()
        dialog.canChooseDirectories = directory
        dialog.canChooseFiles = !directory
        dialog.allowsMultipleSelection = false
        dialog.beginSheetModal(for: window) { result in
            if result == .OK, let url = dialog.url { self.fields[key]?.stringValue = url.path; self.scheduleSave() }
        }
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        if smoke { return true }
        if busy { status.stringValue = "Espera a que termine la operación antes de cerrar."; return false }
        saveTimer?.invalidate()
        closeAfterSave = true
        request("save", payload())
        return false
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    #if LAUNCHER_QA
    func startRegistrationAcceptance() {
        registrationHeartbeatTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { _ in self.registrationHeartbeat += 1 }
        let accountBefore = username.stringValue
        let registerButton = controls.first { ($0 as? NSButton)?.title == "Registrarse" } as? NSButton
        registrationChecks["register_button_available"] = registerButton != nil && registerButton!.isEnabled
        registerButton?.performClick(nil)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
            self.registrationChecks["sheet_attached"] = self.registrationPanel != nil && self.window.attachedSheet === self.registrationPanel
            self.registrationChecks["sheet_visible"] = self.registrationPanel?.isVisible == true
            self.registrationChecks["username_focused"] = self.registrationUsername.currentEditor() != nil
            self.registrationChecks["password_fields_masked"] = self.registrationPassword is NSSecureTextField && self.registrationConfirm is NSSecureTextField
            guard self.registrationPanel != nil else { self.finishRegistrationAcceptance(); return }
            self.registrationUsername.stringValue = "native-modal-test-no-submit"
            self.registrationPassword.stringValue = "fixture-password-one"
            self.registrationConfirm.stringValue = "fixture-password-two"
            self.registrationCreate.performClick(nil)
            self.registrationChecks["mismatch_validated_in_sheet"] = self.registrationStatus.stringValue == "Las contraseñas no coinciden."
            self.registrationChecks["mismatch_keeps_sheet_open"] = self.window.attachedSheet === self.registrationPanel && self.registrationPanel?.isVisible == true
            self.registrationChecks["mismatch_did_not_start_backend"] = !self.busy && self.registrationUnexpectedRequests == 0
            if let panel = self.registrationPanel, let content = panel.contentView,
               let bitmap = content.bitmapImageRepForCachingDisplay(in: content.bounds) {
                content.layoutSubtreeIfNeeded()
                content.cacheDisplay(in: content.bounds, to: bitmap)
                if let data = bitmap.representation(using: .png, properties: [:]), let path = ProcessInfo.processInfo.environment["WAKFU_REGISTRATION_SNAPSHOT"] { try? data.write(to: URL(fileURLWithPath: path)) }
            }
            self.registrationCancel.performClick(nil)
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                self.registrationChecks["cancel_detaches_sheet"] = self.window.attachedSheet == nil && self.registrationPanel == nil
                self.registrationChecks["cancel_preserves_account"] = self.username.stringValue == accountBefore
                (self.controls.first { $0.action == #selector(self.selectPlayTab) } as? NSButton)?.performClick(nil)
                self.registrationChecks["parent_navigation_responsive"] = self.tabs.selectedTabViewItem?.identifier as? String == "play"
                registerButton?.performClick(nil)
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                    self.registrationChecks["sheet_reopens"] = self.registrationPanel?.isVisible == true && self.window.attachedSheet === self.registrationPanel
                    self.registrationChecks["reopened_fields_empty"] = self.registrationUsername.stringValue.isEmpty && self.registrationPassword.stringValue.isEmpty && self.registrationConfirm.stringValue.isEmpty
                    self.registrationCancel.performClick(nil)
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                        self.registrationChecks["second_cancel_detaches_sheet"] = self.registrationPanel == nil && self.window.attachedSheet == nil
                        self.registrationChecks["main_runloop_alive"] = self.registrationHeartbeat >= 8
                        self.registrationChecks["no_backend_or_network_requests"] = self.registrationUnexpectedRequests == 0
                        self.finishRegistrationAcceptance()
                    }
                }
            }
        }
    }

    func finishRegistrationAcceptance() {
        registrationHeartbeatTimer?.invalidate()
        let report: [String: Any] = ["passed": !registrationChecks.isEmpty && registrationChecks.values.allSatisfy { $0 },
                                     "checks": registrationChecks, "heartbeatCount": registrationHeartbeat,
                                     "backendRequests": registrationUnexpectedRequests, "gameStarted": false,
                                     "registrationSubmitted": false]
        if let path = ProcessInfo.processInfo.environment["WAKFU_REGISTRATION_REPORT"],
           let data = try? JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]) { try? data.write(to: URL(fileURLWithPath: path)) }
        NSApp.terminate(nil)
    }
    #endif

    func startWebAcceptance() {
        #if LAUNCHER_QA
        guard let path = ProcessInfo.processInfo.environment["WAKFU_WEB_FIXTURE"],
              let data = try? Data(contentsOf: URL(fileURLWithPath: path)),
              let fixture = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let account = fixture["username"] as? String,
              let secret = fixture["password"] as? String else { NSApp.terminate(nil); return }
        loading = true
        username.stringValue = account
        knownUsername = account
        password.stringValue = secret
        passwordEdited = true
        remember.state = .off
        loading = false
        tabs.selectTabViewItem(at: 1)
        #endif
    }

    func inspectWebAcceptance() {
        #if LAUNCHER_QA
        webSmokeAttempts += 1
        let script = """
        JSON.stringify({title:document.title, origin:location.origin, path:location.pathname,
          hasLogin:!!document.querySelector('input[type=password]'),
          headings:Array.from(document.querySelectorAll('h1,h2,h3')).filter(x=>x.getClientRects().length).slice(0,20).map(x=>x.innerText),
          buttons:Array.from(document.querySelectorAll('button')).filter(x=>x.getClientRects().length).slice(0,12).map(x=>x.innerText),
          hasAchievements:/logros|achievements/i.test(document.body.innerText),
          hasDungeon:/mazmorr|dungeon/i.test(document.body.innerText),
          hasTravelControl:Array.from(document.querySelectorAll('button')).some(x=>x.getClientRects().length && /Ir a la entrada/.test(x.innerText)),
          bodyLength:document.body.innerText.length})
        """
        webView.evaluateJavaScript(script) { result, error in
            let raw = result as? String ?? "{}"
            let object = (raw.data(using: .utf8).flatMap { try? JSONSerialization.jsonObject(with: $0) }) as? [String: Any] ?? [:]
            let ready = object["hasDungeon"] as? Bool == true && object["hasLogin"] as? Bool == false
            if !ready && self.webSmokeAttempts == 1 {
                // Select the existing read-only tab; never click a travel/action button.
                self.webView.evaluateJavaScript("Array.from(document.querySelectorAll('button')).find(x=>/^[\\s♙]*Logros/.test(x.innerText))?.click()")
            }
            if !ready && self.webSmokeAttempts < 5 {
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) { self.inspectWebAcceptance() }
                return
            }
            if let path = ProcessInfo.processInfo.environment["WAKFU_WEB_REPORT"] {
                var report = object
                report["ready"] = ready
                report["attempts"] = self.webSmokeAttempts
                report["javascriptError"] = error != nil
                report["gameStarted"] = false
                report["teleportAttempted"] = false
                if let data = try? JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]) { try? data.write(to: URL(fileURLWithPath: path)) }
            }
            self.webView.takeSnapshot(with: nil) { image, _ in
                if let image = image, let data = image.tiffRepresentation, let bitmap = NSBitmapImageRep(data: data), let png = bitmap.representation(using: .png, properties: [:]), let path = ProcessInfo.processInfo.environment["WAKFU_WEB_SNAPSHOT"] { try? png.write(to: URL(fileURLWithPath: path)) }
                NSApp.terminate(nil)
            }
        }
        #endif
    }

    func saveSnapshotAndExit() {
        #if LAUNCHER_QA
        if let path = ProcessInfo.processInfo.environment["WAKFU_UI_REAL_SNAPSHOT"] {
            let capture = Process()
            capture.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
            capture.arguments = ["-x", "-l\(window.windowNumber)", path]
            try? capture.run()
            capture.waitUntilExit()
        }
        window.contentView?.layoutSubtreeIfNeeded()
        window.contentView?.displayIfNeeded()
        guard let content = window.contentView, let bitmap = content.bitmapImageRepForCachingDisplay(in: content.bounds) else { NSApp.terminate(nil); return }
        content.cacheDisplay(in: content.bounds, to: bitmap)
        if let data = bitmap.representation(using: .png, properties: [:]), let path = ProcessInfo.processInfo.environment["WAKFU_UI_SNAPSHOT"] { try? data.write(to: URL(fileURLWithPath: path)) }
        NSApp.terminate(nil)
        #endif
    }
}

let app = NSApplication.shared
// Apply the appearance before native controls are constructed.
app.appearance = NSAppearance(named: .aqua)
let delegate = Launcher()
app.delegate = delegate
app.run()

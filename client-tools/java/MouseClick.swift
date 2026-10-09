import ApplicationServices
import Foundation

guard CommandLine.arguments.count == 3,
      let x = Double(CommandLine.arguments[1]),
      let y = Double(CommandLine.arguments[2]), AXIsProcessTrusted() else {
    fputs("Usage: mouse-click x y (requires Accessibility permission)\n", stderr)
    exit(1)
}
let point = CGPoint(x: x, y: y)
let source = CGEventSource(stateID: .hidSystemState)
for type in [CGEventType.mouseMoved, .leftMouseDown, .leftMouseUp] {
    guard let event = CGEvent(mouseEventSource: source, mouseType: type,
                              mouseCursorPosition: point, mouseButton: .left) else { exit(1) }
    event.setIntegerValueField(.mouseEventClickState, value: type == .mouseMoved ? 0 : 1)
    event.post(tap: .cghidEventTap)
    usleep(30000)
}

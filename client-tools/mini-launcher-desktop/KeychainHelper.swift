import Foundation
import Security

// Secrets arrive through stdin and stay out of process arguments and diagnostics.
func run() throws -> [String: Any] {
    let input = FileHandle.standardInput.readDataToEndOfFile()
    guard input.count <= 1_048_576,
          let request = try JSONSerialization.jsonObject(with: input) as? [String: String],
          let action = request["action"], let identifier = request["id"],
          identifier.range(of: "^[a-f0-9]{32,64}$", options: .regularExpression) != nil else {
        return ["ok": false]
    }
    let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                               kSecAttrService as String: "net.hectorpulido.wakfu.minilauncher",
                               kSecAttrAccount as String: identifier]
    if action == "get" {
        var lookup = query
        lookup[kSecReturnData as String] = true
        lookup[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(lookup as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data,
              let value = String(data: data, encoding: .utf8) else {
            return ["ok": false, "status": status]
        }
        return ["ok": true, "value": value]
    }
    if action == "set", let value = request["value"] {
        let bytes = Data(value.utf8)
        var status = SecItemUpdate(query as CFDictionary, [kSecValueData as String: bytes] as CFDictionary)
        if status == errSecItemNotFound {
            var item = query
            item[kSecValueData as String] = bytes
            item[kSecAttrLabel as String] = "Wakfu Minilauncher"
            status = SecItemAdd(item as CFDictionary, nil)
        }
        return ["ok": status == errSecSuccess, "status": status]
    }
    if action == "delete" {
        let status = SecItemDelete(query as CFDictionary)
        return ["ok": status == errSecSuccess || status == errSecItemNotFound, "status": status]
    }
    return ["ok": false]
}
do {
    let result = try run()
    FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: result))
    exit(result["ok"] as? Bool == true ? 0 : 1)
} catch {
    FileHandle.standardOutput.write(Data("{\"ok\":false}".utf8))
    exit(1)
}

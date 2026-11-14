import java.lang.instrument.Instrumentation;
import java.net.InetAddress;
import java.security.Permission;
import java.nio.file.*;
import java.util.*;

/** Exact endpoint allowlist plus the loopback launcher bridge. */
@SuppressWarnings("removal")
public final class DropinNetworkGuard extends SecurityManager {
    private static Path audit;
    private static Map<String, Set<Integer>> endpoints;

    public static void premain(String options, Instrumentation instrumentation) throws Exception {
        if (options == null) throw new IllegalArgumentException("Guard configuration missing");
        String[] values = options.split("\\|", -1);
        if (values.length != 3) throw new IllegalArgumentException("Guard configuration missing");
        Path configuredAudit = Path.of(values[0]);
        Map<String, Set<Integer>> configured = new HashMap<>();
        if (values[1].equals("v2")) {
            for (String endpoint : values[2].split(",", -1)) {
                int separator = endpoint.lastIndexOf(':');
                if (separator <= 0) throw new IllegalArgumentException("Invalid guard endpoint");
                add(configured, endpoint.substring(0, separator), endpoint.substring(separator + 1));
            }
        } else {
            for (String port : values[2].split(",", -1)) add(configured, values[1], port);
        }
        // Validate every endpoint before installing the guard; malformed input
        // must never leave a partially configured allowlist.
        for (Map.Entry<String, Set<Integer>> entry : configured.entrySet()) {
            entry.setValue(Set.copyOf(entry.getValue()));
        }
        audit = configuredAudit;
        endpoints = Map.copyOf(configured);
        if (audit.getParent() != null) Files.createDirectories(audit.getParent());
        System.setSecurityManager(new DropinNetworkGuard());
    }

    private static String normalizedHost(String host) {
        if (host == null) return "";
        if (host.startsWith("[") && host.endsWith("]")) host = host.substring(1, host.length() - 1);
        return host.toLowerCase(Locale.ROOT);
    }

    private static void add(Map<String, Set<Integer>> configured, String rawHost, String rawPort) {
        String host = normalizedHost(rawHost);
        if (host.isEmpty() || !host.matches("[a-z0-9._:-]+")) {
            throw new IllegalArgumentException("Invalid guard host");
        }
        if (!rawPort.matches("[0-9]{1,5}")) throw new IllegalArgumentException("Invalid guard port");
        int port = Integer.parseInt(rawPort);
        if (port < 1 || port > 65535) throw new IllegalArgumentException("Invalid guard port");
        configured.computeIfAbsent(host, key -> new HashSet<>()).add(port);
    }

    private static boolean local(String host) {
        host = normalizedHost(host);
        return host.equals("127.0.0.1") || host.equals("localhost") || host.equals("::1")
            || host.equals("0:0:0:0:0:0:0:1");
    }

    @Override public void checkConnect(String host, int port) {
        Set<Integer> allowed = endpoints.get(normalizedHost(host));
        if (local(host) || (allowed != null && (port == -1 || allowed.contains(port)))) return;
        try {
            Files.writeString(audit, java.time.Instant.now() + " blocked host=" + host + " port=" + port + "\n",
                StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (Exception ignored) {}
        throw new SecurityException("Only the configured private server endpoints are allowed");
    }

    @Override public void checkConnect(String host, int port, Object context) { checkConnect(host, port); }
    @Override public void checkAccept(String host, int port) {
        if (!local(host)) throw new SecurityException("Only local launcher accepted");
    }
    @Override public void checkMulticast(InetAddress address) { throw new SecurityException("Multicast denied"); }
    @Override public void checkPermission(Permission permission) {
        if (permission instanceof RuntimePermission && permission.getName().equals("setSecurityManager")) {
            throw new SecurityException("Network guard cannot be removed");
        }
    }
    @Override public void checkPermission(Permission permission, Object context) { checkPermission(permission); }
}

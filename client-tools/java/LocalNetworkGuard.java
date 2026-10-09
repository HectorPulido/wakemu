import java.lang.instrument.Instrumentation;
import java.net.InetAddress;
import java.security.Permission;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

/** Process-local DNS/socket guard. The OS sandbox also covers native sockets. */
@SuppressWarnings("removal")
public final class LocalNetworkGuard extends SecurityManager {
    private static Path audit;
    public static void premain(String path, Instrumentation instrumentation) throws Exception {
        audit = Path.of(path);
        Files.createDirectories(audit.getParent());
        System.setSecurityManager(new LocalNetworkGuard());
        System.err.println("LOCAL NETWORK GUARD ACTIVE: loopback only; external DNS denied");
    }
    private static boolean local(String host) {
        return "127.0.0.1".equals(host) || "localhost".equalsIgnoreCase(host)
            || "::1".equals(host) || "[::1]".equals(host)
            || "0:0:0:0:0:0:0:1".equals(host);
    }
    private static synchronized void reject(String host, int port) {
        try {
            Files.writeString(audit, java.time.Instant.now() + " blocked host=" + host
                + " port=" + port + (port == -1 ? " DNS\n" : " connection\n"),
                StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (Exception ignored) {}
        throw new SecurityException("Local-only experiment: external network denied");
    }
    @Override public void checkPermission(Permission permission) {
        if (permission instanceof RuntimePermission && permission.getName().equals("setSecurityManager"))
            throw new SecurityException("Cannot remove local network guard");
    }
    @Override public void checkPermission(Permission permission, Object context) { checkPermission(permission); }
    @Override public void checkConnect(String host, int port) { if (!local(host)) reject(host, port); }
    @Override public void checkConnect(String host, int port, Object context) { checkConnect(host, port); }
    @Override public void checkAccept(String host, int port) { checkConnect(host, port); }
    @Override public void checkMulticast(InetAddress address) { reject(address.getHostAddress(), -2); }
}

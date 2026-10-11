import java.net.InetAddress;
import java.net.Socket;

@SuppressWarnings("removal")
public final class LocalNetworkGuardTest {
    public static void main(String[] args) throws Exception {
        if (System.getSecurityManager() == null) throw new AssertionError("Missing guard");
        System.getSecurityManager().checkConnect("127.0.0.1", 18083);
        for (String host : new String[]{"haapi.ankama.com", "wakfu-dispatcher.ankama-games.com", "192.0.2.1"}) {
            if (!host.equals("192.0.2.1")) {
                try { InetAddress.getByName(host); throw new AssertionError("External DNS allowed"); }
                catch (SecurityException expected) {}
            }
            try (Socket ignored = new Socket(host, 80)) { throw new AssertionError("External connection allowed"); }
            catch (SecurityException expected) {}
        }
        try { System.setSecurityManager(null); throw new AssertionError("Guard removable"); }
        catch (SecurityException expected) {}
        try (Socket local = new Socket("127.0.0.1", Integer.parseInt(args[0]))) {
            local.getOutputStream().write(1);
        }
        System.out.println("Java guard OK: external DNS/sockets denied; loopback allowed; guard cannot be removed.");
    }
}

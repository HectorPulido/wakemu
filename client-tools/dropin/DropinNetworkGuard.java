import java.lang.instrument.Instrumentation;
import java.net.InetAddress;
import java.security.Permission;
import java.nio.file.*;
import java.util.*;
/** Exact server allowlist plus loopback launcher bridge; native sockets covered by sandbox. */
@SuppressWarnings("removal")
public final class DropinNetworkGuard extends SecurityManager {
 private static Path audit;private static String host;private static final Set<Integer> ports=new HashSet<>();
 public static void premain(String options,Instrumentation instrumentation)throws Exception{
  String[] values=options.split("\\|",3);if(values.length!=3)throw new IllegalArgumentException("Guard configuration missing");
  audit=Path.of(values[0]);host=values[1];for(String port:values[2].split(","))ports.add(Integer.parseInt(port));
  Files.createDirectories(audit.getParent());System.setSecurityManager(new DropinNetworkGuard());
 }
 private static boolean local(String h){return "127.0.0.1".equals(h)||"localhost".equalsIgnoreCase(h)||"::1".equals(h)||"[::1]".equals(h)||"0:0:0:0:0:0:0:1".equals(h);}
 @Override public void checkConnect(String h,int port){
  if(local(h)||(host.equals(h)&&(port==-1||ports.contains(port))))return;
  try{Files.writeString(audit,java.time.Instant.now()+" blocked host="+h+" port="+port+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);}catch(Exception ignored){}
  throw new SecurityException("Only the configured private server is allowed");
 }
 @Override public void checkConnect(String h,int port,Object context){checkConnect(h,port);}
 @Override public void checkAccept(String h,int port){if(!local(h))throw new SecurityException("Only local launcher accepted");}
 @Override public void checkMulticast(InetAddress address){throw new SecurityException("Multicast denied");}
 @Override public void checkPermission(Permission p){if(p instanceof RuntimePermission&&p.getName().equals("setSecurityManager"))throw new SecurityException("Network guard cannot be removed");}
 @Override public void checkPermission(Permission p,Object context){checkPermission(p);}
}

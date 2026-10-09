import java.util.zip.*;
import jdk.internal.org.objectweb.asm.*;
/** Original direct Qu implementations; offline bytecode headers only. */
public class FindNativeAreaRegistrationCallbacks {
 public static void main(String[]args)throws Exception{try(ZipFile zip=new ZipFile("client/lib/wakfu-client.jar")){
  var entries=zip.entries();while(entries.hasMoreElements()){var entry=entries.nextElement();if(!entry.getName().endsWith(".class"))continue;
   ClassReader reader=new ClassReader(zip.getInputStream(entry));for(String iface:reader.getInterfaces())if(iface.equals("Qu"))System.out.println(reader.getClassName());
  }
 }}
}

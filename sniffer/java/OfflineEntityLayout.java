import java.nio.*;
import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
/** Offline protocol research only; never opens a game connection.
 * java -cp '.runtime/local/classes:client/lib/*' OfflineEntityLayout blob.bin
 * Reads the client's section list and reports exact byte boundaries.
 */
public class OfflineEntityLayout {
 public static void main(String[] args) throws Exception {
  Object serializer=Class.forName("eHk").getConstructor().newInstance();
  ByteBuffer bytes=ByteBuffer.wrap(Files.readAllBytes(Path.of(args[0])));
  Class<?> format=Class.forName("eHf"), section=Class.forName("eHe");
  Object variant=format.getEnumConstants()[Byte.toUnsignedInt(bytes.get())];
  System.out.println("Format "+variant);
  Object[] sections=(Object[])format.getMethod("fuK").invoke(variant);
  Method get=Class.forName("eHd").getDeclaredMethod("a",section); get.setAccessible(true);
  Object defaults=Class.forName("eHk").getConstructor().newInstance();
  for(Object key:sections) {
   Object data=get.invoke(serializer,key); int start=bytes.position();
   data.getClass().getMethod("aG",ByteBuffer.class).invoke(data,bytes);
   System.out.println(key+" "+data.getClass().getName()+" "+start+":"+bytes.position());
   if(args.length>1 && args[1].equals("--defaults")) {
    Object empty=get.invoke(defaults,key);
    int size=(Integer)empty.getClass().getMethod("DN").invoke(empty);
    ByteBuffer encoded=ByteBuffer.allocate(size);
    boolean success=(Boolean)empty.getClass().getMethod("aF",ByteBuffer.class).invoke(empty,encoded);
    if(!success || encoded.hasRemaining())throw new IllegalStateException("Incomplete default section "+key);
    System.out.println("DEFAULT "+key+" "+HexFormat.of().formatHex(encoded.array()));
   }
   for(Field f:data.getClass().getDeclaredFields()) {
    if(Modifier.isStatic(f.getModifiers()))continue;
    f.setAccessible(true); Object v=f.get(data);
    if(v==null || v instanceof Number || v instanceof Boolean || v instanceof String || v instanceof Collection || v instanceof Map)
      System.out.println("  "+f.getName()+"="+v);
   }
  }
  System.out.println("Remaining "+bytes.remaining());
 }
}

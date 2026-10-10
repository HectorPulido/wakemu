import java.nio.file.*;
import java.nio.ByteBuffer;
/** Decode the actual ordinary NPC bootstrap/refresh with the shipped client. */
public class ProbeNativeMonsterFightProperties {
 public static void main(String[] args) throws Exception {
  eHj descriptor = new eHj();
  byte[] payload = Files.readAllBytes(Path.of(args[0]));
  ByteBuffer buffer = ByteBuffer.wrap(payload);
  int format = buffer.get() & 255;
  if (format != 2) throw new AssertionError("Ordinary NPC format required");
  var select = eHd.class.getDeclaredMethod("a", eHe.class);
  select.setAccessible(true);
  for (eHe field : eHf.values()[format].fuK()) {
   gp part = (gp)select.invoke(descriptor, field);
   if (!part.aG(buffer)) throw new AssertionError("Native section rejected " + field);
  }
  if (buffer.hasRemaining()) throw new AssertionError("Trailing native actor bytes");
  descriptor.ew(payload);
  rK component = descriptor.ftb();
  if (component.XP == null) throw new AssertionError("Null native fight-property component");
  eHN<ffe> properties = new eHN<>();
  if (!properties.b(component.XP.XT)) throw new AssertionError("Invalid native property snapshot");
  boolean expected = Boolean.parseBoolean(args[1]);
  if (properties.a(ffe.Ua(40)) != expected) throw new AssertionError("Native capture property mismatch");
  System.out.println("PASS ordinary NPC native capture property=" + expected);
 }
}

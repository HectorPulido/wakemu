import java.nio.file.Path;
import java.lang.reflect.Method;
/** Original eZR wire-container dispatch, not a direct bPE/fyW assignment. */
public final class ProbeNativeStateContainerDiscriminator {
 public static void main(String[] args) throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  fyZ.guX().a(new bbV());
  Method decode=eZR.class.getDeclaredMethod("G",int.class,long.class);decode.setAccessible(true);
  for(int ref:new int[]{3442,8913}) {
   fyW expected=((fyW)fyZ.guX().aax(ref)).cu((short)20);
   long identity=expected.QF();
   if(expected.aZY()!=1)throw new AssertionError("fyW discriminator");
   eYg good=new eYg(); decode.invoke(good,1,identity);
   if(!(good.bbe() instanceof fyW))throw new AssertionError("wire1 did not resolve fyW");
   if(((fyW)good.bbe()).guI()!=ref || ((fyW)good.bbe()).cmZ()!=20)throw new AssertionError("wrong state/level");
   eYg area=new eYg();decode.invoke(area,3,identity);
   if(area.bbe()!=null)throw new AssertionError("wire3 unexpectedly resolved state");
   System.out.println("PASS state="+ref+" wire1=fyW wire3=missing Qs area");
  }
 }
}

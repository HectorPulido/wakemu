import java.nio.file.Path;
/** Offline real native state template; zero is retained, not promoted to one. */
public class ProbeNativeZeroState {
 public static void main(String[] args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  fyZ.guX().a(new bbV());
  for(int reference:new int[]{9312,9314,9324}) {
   fyW state=fyZ.guX().aax(reference);
   if(state==null)throw new AssertionError("missing native state "+reference);
   fyW zero=state.cu((short)0);
   if(zero.cmZ()!=0 || fyW.aaf(fyW.ae((short)reference,(short)0))!=0)throw new AssertionError("zero rewritten");
   System.out.println("native state "+reference+" level0 retained; packed level0 roundtrip");
  }
 }
}

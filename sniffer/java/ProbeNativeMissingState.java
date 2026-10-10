import java.nio.file.Path;
/** Offline native lookup and carrier constructor for source-attested absence. */
public class ProbeNativeMissingState {
 public static void main(String[] args) throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  fyZ.guX().a(new bbV());
  if(fyZ.guX().aax(759)!=null)throw new AssertionError("759 unexpectedly exists");
  for(short level:new short[]{0,1,20,200,245,250,32767}) {
   eZk carrier=eZk.a(bcz.dcW(),null,null,fyW.ae((short)759,level));
   if(carrier!=null)throw new AssertionError("absent native state manufactured");
  }
  if(fyZ.guX().aax(3702)==null||fyZ.guX().aax(4464)==null)throw new AssertionError("native Sacrier innates missing");
  System.out.println("PASS: native759 absent; eZk.a returns null at7levels;3702/4464 exist");
 }
}

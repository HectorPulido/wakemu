import java.nio.file.*;
import java.lang.reflect.*;
/** Original common state opening group; no scene, sockets, or running client. */
public class ProbeNativeOpeningGroupRoute {
 public static void main(String[]args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  eVn definition=bcA.dcX().AH(327548);
  eYm runner=new eYm();Field pk=Qe.class.getDeclaredField("bfp");pk.setAccessible(true);pk.set(runner,definition);
  if(definition.awM()!=999||definition.So(2)!=10||runner.bbA()||runner.bbB())throw new AssertionError("opening route changed");
  System.out.println("PASS original327548 family999 So(2)=10 bbA=false bbB=false; not a0/1 enum");
 }
}

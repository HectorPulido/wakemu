import java.nio.file.Path;
public class ProbeNativeGrantedLevel {
 public static void main(String[] args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  for(int reference:new int[]{5345,5624,3909}) {
   bPO level=bPS.elL().i(reference,(short)200);
   int expected=Math.min(200,bPS.elL().IP(reference).Fq());
   if(level.cmZ()!=expected)throw new AssertionError(reference+" level="+level.cmZ());
   System.out.println(reference+" requested200 actual="+level.cmZ()+" max="+level.aWa());
  }
 }
}

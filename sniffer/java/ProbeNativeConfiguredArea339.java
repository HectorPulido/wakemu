import java.nio.file.*;
import java.util.*;
/** Original339 runner configuration and target definition shape, offline. */
public class ProbeNativeConfiguredArea339 {
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX raw){}});
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw raw){}});
  eZR runner=eVi.fLJ().pS(339);
  System.out.println("339 runner="+runner.getClass().getName()+" bbz="+runner.bbz()+" bbA="+runner.bbA()+" bbB="+runner.bbB());
  for(String reference:args){eVn effect=bcA.dcX().AH(Integer.parseInt(reference));
   for(short level:new short[]{1,30,200}){
    List<Integer> values=new ArrayList<>();for(int i=0;i<effect.fKJ();i++)values.add(effect.a(i,level,eVh.rpA));
    System.out.println(reference+" family="+effect.awM()+" level="+level+" values="+values);
   }
  }
 }
}

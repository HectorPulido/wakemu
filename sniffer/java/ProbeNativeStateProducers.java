import java.nio.file.*;
public class ProbeNativeStateProducers {
 public static void main(String[]args)throws Exception{
  int state=Integer.parseInt(args[0]);
  java.util.Set<Integer> producers=new java.util.HashSet<>();
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw raw){
   eVn e=bcA.dcX().AH(raw.aZE());
   if(e.awM()==304&&e.fKJ()>0&&e.a(0,(short)1,eVh.rpA)==state)
    {producers.add(raw.aZE());System.out.println("producer="+raw.aZE()+" criteria="+raw.cyi()+" count="+e.fKJ());}
  }});
  java.util.Map<Integer,int[]> groups=new java.util.TreeMap<>();
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX g){groups.put(g.d(),g.cku());}});
  for(int pass=0;pass<10;pass++){
   java.util.Set<Integer> next=new java.util.HashSet<>();
   for(var g:groups.entrySet())for(int child:g.getValue())if(producers.contains(child)&&!producers.contains(g.getKey())){
    next.add(g.getKey());System.out.println("parent="+g.getKey()+" child="+child);
   }
   if(next.isEmpty())break;producers.addAll(next);
  }
  for(int ref:producers){eVn e=bcA.dcX().AH(ref);System.out.println("definition="+ref+" class="+e.awM()+" area="+e.aZP().bEm()+" masks="+e.aZL());}

 }
}

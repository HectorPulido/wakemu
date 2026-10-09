import java.nio.file.*;
import java.lang.reflect.Method;
import java.util.*;

/** Inspects installed fbd wall prototypes and their cloned constructor state. */
public class ProbeNativeWallArea {
 static final class Owner extends biw {
  public byte bcM(){return 0;}
  public long Sn(){return 7;}
  public Qf bax(){return null;}
 }
 public static void main(String[] args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Set<Integer> wanted=new LinkedHashSet<>();
  for(String value:args) wanted.add(Integer.parseInt(value));
  Map<Integer,faV> prototypes=new HashMap<>();
  apw.bGL().a(new aKa(),new apB<aKa>(){public void load(aKa raw){
   if(wanted.contains(raw.d())) prototypes.put(raw.d(),bcN.hFx.a(raw));
  }});
  Owner owner=new Owner();
  Method qfChannel=Qq.class.getDeclaredMethod("bcx");
  qfChannel.setAccessible(true);
  Map<Integer,String> characteristicNames=new HashMap<>();
  for(ffw stat:ffw.values()) characteristicNames.put((int)stat.aKg(), stat.name());
  for(int reference:wanted){
   faV prototype=prototypes.get(reference);
   if(prototype==null){System.out.println(reference+" absent");continue;}
   for(short level:new short[]{1,30,200}){
    faV area=prototype.b(new fbm(reference+900,2,3,level,null,7,owner,level,aAS.wL(7)));
    fbd wall=(fbd)area;
    PA hp=wall.b(ffw.sgC);
    List<String> stats=new ArrayList<>();
    gnu.trove.iterator.TIntObjectIterator<PA> statRows=wall.fTp().esd();
    while(statRows.hasNext()){
     statRows.advance(); PA value=statRows.value();
     stats.add(characteristicNames.getOrDefault(statRows.key(), "?")+"#"+statRows.key()
       +":"+value.aYS()+"/"+value.aYU());
    }
    System.out.println(reference+" class="+area.getClass().getName()+" type="+area.aeV()
      +" level="+level+" statPresent="+wall.a(ffw.sgC)+" hp="+hp.aYS()
      +" PA="+hp.getClass().getName()+" hpBounds="+hp.aYT()+":"+hp.aYU()+":"+hp.aYV()+":"+hp.aYW()+" obstacle="+area.bcO()
      +" movement="+area.bcP()+" los="+area.fTq()+" bcJ="+area.bcJ()
      +" Qf="+(area.bax()!=null)+" Qq_bcx="+qfChannel.invoke(area)+" bcK="+area.bcK()
      +" baF="+area.baF()+" baG="+area.baG()+" baK="+area.baK()
      +" baD="+wall.baD()+" targetStatSGM="+wall.a(ffw.sgM)
      +" ownerApplicable="+area.e((amP)owner)+" targets="+wall.n((amP)owner).size());
    System.out.println("  characteristics="+stats);
   }
  }
 }
}

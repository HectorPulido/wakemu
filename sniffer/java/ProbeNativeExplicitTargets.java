import java.lang.reflect.*;import java.util.*;
/** Execute Qe.a's real explicit-PV/aZX branch; no simulated branch decision. */
public class ProbeNativeExplicitTargets {
 static class Runner extends eXE {
  final List<Long> selected=new ArrayList<>();final PV areaActor;
  Runner(PV actor){areaActor=actor;}
  public void g(PV target){selected.add(target.Sn());}
  public boolean d(Collection<PV> actors){for(PV actor:actors)selected.add(actor.Sn());return true;}
  public List<PV> a(eVn definition,amP caster,PN<eVn> context,int x,int y,short z){return List.of(areaActor);}
 }
 static PV actor(long id){return(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->{
  if(m.getName().equals("Sn"))return id;
  if(m.getName().equals("hashCode"))return Long.hashCode(id);
  if(m.getName().equals("equals"))return p==a[0];
  throw new UnsupportedOperationException(m.getName());});}
 public static void main(String[]args){
  PV caster=actor(7),area=actor(8);
  for(boolean recalculate:new boolean[]{false,true})for(boolean explicit:new boolean[]{false,true}){
   eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->switch(m.getName()){
    case"aZS"->(short)0;case"aZX"->recalculate;case"cyc"->0f;default->throw new UnsupportedOperationException(m.getName());});
   Runner runner=new Runner(area);
   runner.a(definition,null,null,caster,8,8,(short)0,explicit?caster:null,new eVt());
   List<Long> expected=List.of(explicit&&!recalculate?7L:8L);
   if(!runner.selected.equals(expected))throw new AssertionError(runner.selected+" != "+expected);
  }
  System.out.println("Native Qe.a explicit PV/aZX 4 branches PASS");
 }
}

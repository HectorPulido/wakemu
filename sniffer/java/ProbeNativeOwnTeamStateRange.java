import java.util.*;import java.lang.reflect.*;import java.nio.file.Path;
/** Actual eKS/eLr Qf selection: caster affiliation, not recipient team. */
public class ProbeNativeOwnTeamStateRange {
 static PV actor(long id,byte team){return (PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class,eHg.class,amO.class},(p,m,a)->switch(m.getName()){case "Sn"->id;case "bcM"->team;case "bcz","bcA"->0;case "bcB"->(short)0;default->throw new UnsupportedOperationException(m.getName());});}
 static boolean match(PV queryCaster,eZV effects,long level)throws Exception{
  List<alS> args=new ArrayList<>(List.of(new alw(3),new amc("caster"),new alw(3442)));
  if(level>=0)args.add(new alw(level));
  eKS query=new eKS(args);Method method=eLr.class.getDeclaredMethod("a",eHg.class,eZV.class);method.setAccessible(true);return (boolean)method.invoke(query,queryCaster,effects);
 }
 static eZV manager(PV recipient,PV caster)throws Exception{
  eZV manager=new eZV(recipient);eZk carrier=eZk.a(null,caster,null,fyW.ae((short)3442,(short)1));carrier.dg(100);
  Field rows=Qf.class.getDeclaredField("bfT");rows.setAccessible(true);((Map<Long,Qe>)rows.get(manager)).put(100L,carrier);return manager;
 }
 public static void main(String[]unused)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");fyZ.guX().a(new bbV());
  PV own=actor(7,(byte)0),foe=actor(-7,(byte)1);int checks=0;
  for(PV recipient:new PV[]{own,foe})for(PV source:new PV[]{own,foe,null}){
   boolean expected=source==own;boolean got=match(own,manager(recipient,source),-1);if(got!=expected)throw new AssertionError();checks++;
  }
  eZV effects=manager(foe,own);if(!match(own,effects,1)||match(own,effects,2)||match(null,effects,-1))throw new AssertionError();checks+=3;
  System.out.println("Native eKS caster affiliation across recipients/null/exact level: "+checks+" PASS");
 }
}

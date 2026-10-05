import java.nio.file.*;
import java.lang.reflect.*;
public class ProbeNativeStateQueue {
 static class Collection extends eZV {Collection(){super(null);}}
 static class Complete extends aVo {final buQ world;Complete(eZR r,PV caster,PV target){super(1,0,310,7,r,false);PW actors=(PW)Proxy.newProxyInstance(PW.class.getClassLoader(),new Class[]{PW.class},(p,m,a)->m.getName().equals("de")?(((Long)a[0])==caster.Sn()?caster:((Long)a[0])==target.Sn()?target:null):null); PN context=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(p,m,a)->m.getName().equals("bae")?actors:m.invoke(bcz.dcW(),a));world=(buQ)Proxy.newProxyInstance(buQ.class.getClassLoader(),new Class[]{buQ.class},(p,m,a)->switch(m.getName()){case "bbg"->context;case "equals"->p==a[0];default->null;});}protected buQ cjD(){return world;}}
 static class Observe extends aTR {Observe(eZR r){super(1,0,7,310,r);}void observe(){super.cbj();}}
 static void set(Object o,Class<?> c,String n,Object v)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 static PV actor(long id,Collection list){return (PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->switch(m.getName()){
  case "Sn"->id;case "bax"->list;case "bcz","bcA"->0;case "bcB"->(short)0;case "bcy"->aAS.dyA;case "toString"->"Actor"+id;default->throw new UnsupportedOperationException(m.getName());});}
 static eZk decoded(byte[] body,PV caster,PV target)throws Exception{
  eZk r=new eZk();r.lV(310);r.a(bcz.dcW());if(r.ds(body)==null)throw new AssertionError("codec");
  set(r,Qe.class,"bfr",caster);set(r,Qe.class,"bfs",target);return r;
 }
 public static void main(String[] args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");fyZ.guX().a(new bbV());
  for(String file:args){byte[] input=Files.readAllBytes(Path.of(file));cvX packet=new cvX();if(!packet.dp(input)||packet.awM()!=310||packet.eIK())throw new AssertionError("cvX carrier wrapper");byte[] body=packet.eIJ();Collection c=new Collection(),t=new Collection();PV caster=actor(20,c),target=actor(-200,t);
   eZk old=decoded(body,caster,target);System.out.println("PK="+old.baZ()+" container="+old.bbe()+" nativeScript="+((eVn)old.baZ()).cbx());old.bbq();new Observe(old).observe();if(t.fSs().size()!=0)throw new AssertionError("old observation registered state");
   eZk fixed=decoded(body,caster,target);aVo action=new Complete(fixed,caster,target);
   action.cYb(); action.fe(target.Sn()); action.iD(caster.Sn()); aER queue=new aER(); queue.c(action); queue.cbu(); if(!queue.cbt().isEmpty()) throw new AssertionError("Native carrier action queue did not drain");
   if(t.fSs().size()!=1||t.fSs().get(0)!=fixed||fixed.bbs())throw new AssertionError("state not retained or gameplay enabled");
   System.out.println("PASS state"+fixed.fQW().guI()+" level"+fixed.fQW().cmZ()+":13497 registrations0;12613 registrations1;real eZV.fSs retained with gameplay disabled");
  }
 }
}

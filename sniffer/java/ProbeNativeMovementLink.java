import java.lang.reflect.*;import java.util.*;
/** Real eXA application/removal using owned native eGj actors and PB facts. */
public class ProbeNativeMovementLink {
 static class A extends ProbeNativeFightersBreedRange.A {
  byte team;Set<PE> properties;M manager;
  public Qf bax(){return manager;}
  public byte bcM(){return team;}
  public boolean a(PE property){return properties.contains(property);}
 }
 static class M extends Qf {PL removed;boolean forced;public Qi bci(){return null;}
  public void a(PL container,boolean flag){removed=container;forced=flag;}}
 static A actor(int team,PE...properties)throws Exception{
  A a=(A)ProbeNativeFightersBreedRange.U.allocateInstance(A.class);a.team=(byte)team;a.properties=new HashSet<>(List.of(properties));a.manager=new M();return a;
 }
 static eXA runner(A source,A target,boolean ignore)throws Exception{
  eXA r=new eXA();for(String name:new String[]{"bfr","bfs"}){Field f=Qe.class.getDeclaredField(name);f.setAccessible(true);f.set(r,name.equals("bfr")?source:target);}
  Field f=Qe.class.getDeclaredField("bfp");f.setAccessible(true);f.set(r,Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},(p,m,a)->{
   if(m.getName().equals("a")&&a.length==1&&a[0] instanceof eVl)return ignore&&a[0]==eVl.rxg;
   throw new UnsupportedOperationException(m.getName());}));return r;
 }
 static boolean link(A s,A t,boolean ignore)throws Exception{
  eXA r=runner(s,t,ignore);Method c=eXA.class.getDeclaredMethod("c",Qe.class,boolean.class);c.setAccessible(true);c.invoke(r,null,true);
  boolean linked=s.frx()==t&&t.frx()==s;
  Field executed=Qe.class.getDeclaredField("bfD");executed.setAccessible(true);executed.set(r,false);r.bbR();
  if(s.frx()!=null||t.frx()!=null)throw new AssertionError("removal");return linked;
 }
 public static void main(String[]args)throws Exception{
  Field events=Qe.class.getDeclaredField("bfA");events.setAccessible(true);
  if(!events.get(new eXA()).equals(Set.of(0,2123)))throw new AssertionError("events");
  if(!link(actor(0),actor(1),false))throw new AssertionError();
  if(link(actor(0,ffe.sdI),actor(1),false))throw new AssertionError();
  if(link(actor(0),actor(1,ffe.sfA),false))throw new AssertionError();
  if(link(actor(0),actor(0,ffe.sfB),false))throw new AssertionError();
  if(!link(actor(0,ffe.sdI),actor(1,ffe.sfA),true))throw new AssertionError();
  for(boolean ownSource:new boolean[]{false,true}){
   A s=actor(0),t=actor(1);eXA r=runner(s,t,false);
   Method c=eXA.class.getDeclaredMethod("c",Qe.class,boolean.class);c.setAccessible(true);c.invoke(r,null,true);
   PL container=(PL)Proxy.newProxyInstance(PL.class.getClassLoader(),new Class<?>[]{PL.class},(p,m,a)->null);
   Field f=Qe.class.getDeclaredField("bfq");f.setAccessible(true);f.set(r,container);
   f=Qe.class.getDeclaredField("bfv");f.setAccessible(true);f.set(r,ownSource?s.manager:t.manager);
   r.bbR();M other=ownSource?t.manager:s.manager;
   if(other.removed!=container||!other.forced||s.frx()!=null||t.frx()!=null)throw new AssertionError("counter-manager removal");
  }
  System.out.println("Native eXA apply/removal/stabilization +other-manager container removal:8PASS; ignoreFlag="+eVl.rxg.fLK());
 }
}

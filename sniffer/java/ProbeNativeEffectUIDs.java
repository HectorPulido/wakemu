import java.lang.reflect.*;import java.util.*;
public class ProbeNativeEffectUIDs {
 static long next=901;
 static PV actor(long id){return(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->switch(m.getName()){
  case "toString"->"Actor"+id;case "Sn"->id;case "bcz","bcA"->0;case "bcB"->(short)0;case "baK"->false;default->throw new UnsupportedOperationException(m.getName());});}
 static eVv definition(){return(eVv)Proxy.newProxyInstance(eVv.class.getClassLoader(),new Class[]{eVv.class},(p,m,a)->switch(m.getName()){
  case "aZD"->(byte)2;case "en","eo"->Tt.pz(0);case "aZO"->new BitSet();case "toString"->"NativeDefinition";case "aZE"->123;case "aZV"->Qd.bfe;case "aZW"->Qb.beO;default->throw new UnsupportedOperationException(m.getName());});}
 static class Group extends eYg {
  static long cloneUid,cloneBase;static boolean cloneRetained;
  public Group fPD(){return new Group();}
  public boolean i(Qe source){return true;}
  protected void c(Qe source,boolean fromEvent){cloneUid=LV();cloneBase=bca().Qq();cloneRetained=Ty();mu(true);}
  public boolean bbA(){return true;}public boolean bbz(){return true;}public boolean bbB(){return true;}
  protected boolean bbZ(){return false;}
  public boolean L(byte channel){return false;}
  void actors(){bfr=actor(7);bfs=actor(-7);bfp=definition();}
 }
 public static void main(String[]args){
  org.apache.log4j.BasicConfigurator.configure();Qe.a(()->next++);
  Group prototype=new Group();prototype.actors();
  Group fresh=(Group)prototype.bbm();
  if(fresh.LV()!=901||fresh.bca().Qq()!=901)throw new AssertionError("fresh UID/base");
  fresh.k(prototype);
  if(Group.cloneUid!=902||Group.cloneBase!=901||Group.cloneRetained)throw new AssertionError("event clone identity/retention");
  System.out.println("fresh UID901/base901; event clone UID902/base901; native Ty=false");
  Qe.a((Qh)null);
 }
}

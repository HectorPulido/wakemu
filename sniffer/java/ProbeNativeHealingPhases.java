import java.lang.reflect.*;import java.util.*;
/** Actual Qe.d -> eZR.n/bbJ -> eZR.a/Qe.a routing with explicit arithmetic fixtures. */
public class ProbeNativeHealingPhases {
 static final List<String> seen=new ArrayList<>();static long next=900;
 static PV actor(long id){return(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->switch(m.getName()){
  case "toString"->"Actor"+id;case "equals"->p==a[0];case "hashCode"->System.identityHashCode(p);case "Sn"->id;case "baK","baG"->false;
  case "a"->{if(a.length==3&&a[0] instanceof BitSet){seen.add(id+":"+a[2]+":"+((Qe)a[1]).getValue());yield false;}yield true;}
  case "bax"->null;default->throw new UnsupportedOperationException(m.getName());});}
 static class Heal extends eXs {
  public Heal(){super(eVg.values()[0],far.rJU);}
  public Heal fOy(){return new Heal();}
  public void C(Qe source){ow(42);}
  protected void c(Qe source,boolean event){ow(7);mu(true);}
  public boolean bbH(){return true;}
  public boolean bbz(){return true;}public boolean bbA(){return true;}public boolean bbB(){return false;}
  protected boolean bbZ(){return false;}
  void setup(){bfr=actor(7);bfs=actor(-7);}
 }
 public static void main(String[]args){Qe.a(()->next++);Heal heal=new Heal();heal.setup();heal.g(heal.bbc());
  var expected=List.of("7:10:0","-7:1:0","7:20:42","-7:2:42","7:30:7","-7:3:7","7:40:7","-7:4:7");
  if(!seen.equals(expected))throw new AssertionError(seen);System.out.println(seen);Qe.a((Qh)null);
 }
}

import java.util.*;
public class ProbeNativeAreaRemovalMasks {
 static final List<String> order=new ArrayList<>();
 static final class Manager extends eZV { Manager(){super(null);} public boolean q(Qe e){order.add("remove");return true;} }
 static final class Parent extends eYQ { final Manager manager=new Manager(); public Qf bbp(){return manager;} }
 static final class Area extends faZ {
  protected Qq bcs(){return new Area();}
  public int aeV(){return 0;}
  public boolean bcv(){return true;}
  public boolean bcw(){return false;}
  public int df(long n){return 0;}
  public byte bav(){return 2;}
  public byte[] baz(){return new byte[0];}
  public anS bEs(){return null;}
  int entries, exits; Area(){super();bgS=new BitSet();bgT=new BitSet();bgS.set(10001);bgT.set(10002);}
  public boolean a(Qe source,amP target){entries++;order.add("enter");return true;}
  public void g(amP target){exits++;order.add("exit");}
  public long[] c(amP target){return new long[0];}
  public java.util.List<amP> d(amP target){return List.of();}
  public void a(int x,int y,short z,Qe source){}
  public boolean e(amP target){return true;}
  public void f(amP target){}
 }
 public static void main(String[] args){
 Area a=new Area(); a.a(new Parent()); BitSet removal=new BitSet();removal.set(10010);a.f(removal);
 BitSet mask=new BitSet();mask.set(10001);mask.set(10002);mask.set(10010);
 a.a(mask,null,null);if(!order.equals(List.of("enter","exit","remove")))throw new AssertionError(order);
 order.clear();a.a(9999,null,null);if(!order.isEmpty())throw new AssertionError(order);
 a.a(10010,null,null);if(!order.equals(List.of("remove")))throw new AssertionError(order);
 System.out.println("PASS native faV rLR mask: entry/exit precede exact parent Qf removal; irrelevant mask does nothing");
 }
}

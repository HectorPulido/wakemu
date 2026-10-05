import java.util.*;
public class ProbeNativeAreaCallbacks {
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
  public boolean a(Qe source,amP target){entries++;return true;}
  public void g(amP target){exits++;}
  public long[] c(amP target){return new long[0];}
  public java.util.List<amP> d(amP target){return List.of();}
  public void a(int x,int y,short z,Qe source){}
  public boolean e(amP target){return true;}
  public void f(amP target){}
 }
 public static void main(String[] args){Area a=new Area();a.a(10001,null,null);if(a.entries!=1||a.exits!=0)throw new AssertionError();a.a(10002,null,null);if(a.entries!=1||a.exits!=1)throw new AssertionError();a.a(9999,null,null);if(a.entries!=1||a.exits!=1)throw new AssertionError();BitSet both=new BitSet();both.set(10001);both.set(10002);a.a(both,null,null);if(a.entries!=2||a.exits!=2)throw new AssertionError();System.out.println("PASS Qq native event-mask routing: entry, exit, irrelevant, combined");}
}

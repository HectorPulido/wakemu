import java.lang.reflect.*;
import java.util.Arrays;
/** Actual Tc/feq insertion and per-round reset; no inferred removal. */
public class ProbeNativePropertyTimeline {
 static void check(Tc timeline,long...ids){if(!Arrays.equals(timeline.biq().toArray(),ids))throw new AssertionError(Arrays.toString(timeline.biq().toArray()));}
 public static void main(String[]args)throws Exception{
  fce context=(fce)Proxy.newProxyInstance(fce.class.getClassLoader(),new Class[]{fce.class},(p,m,a)->{
   if(m.getName().equals("d"))return 12;
   throw new UnsupportedOperationException(m.getName());});
  feq policy=new feq(context,null);Tc timeline=new Tc(policy);
  timeline.biq().add(new long[]{7,-7,8});timeline.bir().add(new long[]{7,-7,8});
  Field cursor=Tc.class.getDeclaredField("bsx");cursor.setAccessible(true);cursor.setByte(timeline,(byte)1);
  int slot=timeline.a(new SQ(1,SR.brt));
  if(slot!=2)throw new AssertionError("native current-relative slot"+slot);
  timeline.p(7,slot);check(timeline,7,-7,7,8);
  timeline.bip();check(timeline,7,-7,7,8); // feq.c is a genuine no-op.
  timeline.bhP();check(timeline,7,-7,8);
  // A fresh summon after an extra turn is inserted into both native lists.
  timeline.biq().clear();timeline.bir().clear();
  timeline.biq().add(new long[]{7,-7,7,8});timeline.bir().add(new long[]{7,-7,8});
  cursor.setByte(timeline,(byte)2);
  timeline.a(901,(short)1,new SQ(1,SR.brt));
  check(timeline,7,-7,7,901,8);
  if(!Arrays.equals(timeline.bir().toArray(),new long[]{7,-7,901,8}))throw new AssertionError("native base insertion");
  timeline.bhP();check(timeline,7,-7,901,8);
  System.out.println("PASS native Tc extra insertion, HASTE, reset and fresh summon base insertion");
 }
}

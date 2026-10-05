import java.util.Arrays;
/** Native Tc/SQ/SX insertion of a fresh UID, no graphics or game packets. */
public class ProbeNativeSummonTimeline {
 static class Hooks extends SZ {
  protected void a(SX x){} protected void b(SX x){} protected void c(SX x){}
  protected void a(SX x,long id){} protected void a(SX x,long id,int n){}
  protected void b(SX x,long id,int n){}
 }
 static void check(int mode,int offset,int expected)throws Exception {
  fce source=(fce)java.lang.reflect.Proxy.newProxyInstance(fce.class.getClassLoader(),new Class[]{fce.class},(o,m,a)->m.getName().equals("d")?1:null);
  fev stats=(fev)java.lang.reflect.Proxy.newProxyInstance(fev.class.getClassLoader(),new Class[]{fev.class},(o,m,a)->m.getName().equals("rI")?false:0);
  Tc timeline=new Tc(new feq(source,stats));timeline.bsw.bhH().add(new long[]{7,-7,8});
  timeline.bsx=1;
  SQ options=new SQ();options.a(SR.pv(mode));options.pt(offset);options.ej(7);
  if(timeline.a(options)!=expected)throw new AssertionError("index");
  timeline.a(901,(short)0,options);
  long[] expectedOrder=new long[4];long[] before={7,-7,8};
  for(int i=0,j=0;i<4;i++)expectedOrder[i]=i==expected?901:before[j++];
  if(!Arrays.equals(timeline.bsw.bhH().toArray(),expectedOrder))
   throw new AssertionError(Arrays.toString(timeline.bsw.bhH().toArray()));
  if(timeline.bik()!=(expected<=1?2:1))throw new AssertionError("current index");
 }
 public static void main(String[]args)throws Exception {
  check(0,1,2);check(1,-1,3);check(2,1,1);check(0,Integer.MAX_VALUE,0);
  System.out.println("PASS native Tc/SQ fresh insertion, anchors, floorMod/int overflow and current preservation");
 }
}

import java.lang.reflect.*;
import java.util.*;
/** Original eWW C, L2 value, percent conversion, eWQ actual and retirement. */
public final class ProbeNativeCurrentStatTriggerValue {
 public static void main(String[]args)throws Exception {
  ffw stat=ffw.fK((byte)20);
  Method apply=eWW.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);
  Method retire=eWQ.class.getDeclaredMethod("fNM");retire.setAccessible(true);
  for(boolean post:new boolean[]{false,true}) {
   Map<PC,fff> target=new HashMap<>();fff pa=new fff(stat,0,100);pa.or(100);pa.on(80);target.put(stat,pa);
   eVn def=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},(p,m,a)->switch(m.getName()){
    case "fKJ"->2;case "aZE"->123456;case "a"->new int[]{10,1}[(int)a[0]];
    default->throw new UnsupportedOperationException(m.getName());});
   eWQ r=new eWQ(stat);
   ProbeNativeArmor.set(r,Qe.class,"bfp",def);
   ProbeNativeArmor.set(r,Qe.class,"bfr",ProbeNativeArmor.actor(new HashMap<>(),0));
   ProbeNativeArmor.set(r,Qe.class,"bfs",ProbeNativeArmor.actor(target,1));
   r.a(1,100f,false);r.C(null); // L1 amount is overwritten by C10.
   if(r.getValue()!=10||r.Mt()!=10)throw new AssertionError("C/Mt");
   if(!post)r.a(1,15f,false); // L2 changes percent10 ->25.
   apply.invoke(r,null,false);
   int applied=r.getValue(),after=pa.aYS();
   if(post)r.a(1,15f,false); // L3 changes actual8 ->23 without PA application.
   int finalAmount=r.getValue();retire.invoke(r);
   if(after!=(post?88:100)||applied!=(post?8:20)||finalAmount!=(post?23:20)||pa.aYS()!=(post?65:80)||r.Mt()!=10)
    throw new AssertionError("native percent ordering");
   System.out.println("PASS "+(post?"L3":"L2")+" applied="+applied+" ledger="+finalAmount+" stat="+after+" retired="+pa.aYS()+" Mt10");
  }
 }
}

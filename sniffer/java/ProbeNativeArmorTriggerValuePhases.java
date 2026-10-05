import java.util.*;
import java.lang.reflect.*;
/** Original eWx/eWW application and retirement around L2/L3 value changes. */
public class ProbeNativeArmorTriggerValuePhases {
 static eWx runner(Map<PC,fff> target)throws Exception {
  eVn def=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},(p,m,a)->switch(m.getName()){
   case "fKJ"->2; case "aZE"->123456;
   case "a"->new int[]{100,0}[(int)a[0]];
   default->throw new UnsupportedOperationException(m.getName());});
  eWx r=new eWx();
  ProbeNativeArmor.set(r,Qe.class,"bfp",def);
  ProbeNativeArmor.set(r,Qe.class,"bfr",ProbeNativeArmor.actor(new HashMap<>(),0));
  ProbeNativeArmor.set(r,Qe.class,"bfs",ProbeNativeArmor.actor(target,1));
  r.lV(1013); r.dg(902);r.dj(902);r.C(null);return r;
 }
 public static void main(String[]args)throws Exception {
  Method apply=eWx.class.getDeclaredMethod("d",PA.class);apply.setAccessible(true);
  Method remove=eWQ.class.getDeclaredMethod("fNM");remove.setAccessible(true);
  Field suppress=eZR.class.getDeclaredField("rIW");suppress.setAccessible(true);
  for(boolean post:new boolean[]{false,true}) {
   Map<PC,fff> stats=new HashMap<>();ProbeCombatArithmetic.put(stats,ffw.shQ,200);
   eWx r=runner(stats);PA pa=stats.get(ffw.shQ);
   if(!post)r.a(1,25f,false); // L2: calculated100 ->125 before d
   apply.invoke(r,pa);int applied=r.getValue(),after=pa.aYS();
   if(post)r.a(1,25f,false); // L3: actual100 ->125 after d
   int retained=r.getValue();remove.invoke(r);
   int expectedAfter=post?300:325,expectedFinal=post?175:200;
   if(after!=expectedAfter||retained!=125||pa.aYS()!=expectedFinal)throw new AssertionError("phase mismatch");
   System.out.println((post?"L3":"L2")+" applied="+applied+" retained="+retained+" after="+after+" retired="+pa.aYS());
  }
  Map<PC,fff> stats=new HashMap<>();ProbeCombatArithmetic.put(stats,ffw.shQ,200);
  eWx r=runner(stats);r.a(1,0f,true);
  if(r.getValue()!=0||!suppress.getBoolean(r))throw new AssertionError("zero suppression");
  r.a(1,10f,true);
  if(r.getValue()!=10||!suppress.getBoolean(r))throw new AssertionError("suppression must remain sticky");
  apply.invoke(r,stats.get(ffw.shQ));
  if(stats.get(ffw.shQ).aYS()!=210)throw new AssertionError("suppression must not cancel application");
  System.out.println("zero->10 sticky notification suppression; application still+10 PASS");
 }
}

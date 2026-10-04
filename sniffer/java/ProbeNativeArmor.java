import java.util.*;
import java.lang.reflect.*;
/** Exact eWx1013 arithmetic and AdditionalDatas cap; ordinary native PV. */
public class ProbeNativeArmor {
 static void set(Object o,Class<?> c,String n,Object v)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 static PV actor(Map<PC,fff>s,int x){PV base=ProbeCombatArithmetic.actor(s,x);return(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class<?>[]{PV.class},(p,m,a)->m.getName().equals("bav")?(byte)0:m.invoke(base,a));}
 public static void main(String[]args)throws Exception{
  for(ffw stat:new ffw[]{ffw.shH,ffw.shI,ffw.shQ,ffw.sim,ffw.sin,ffw.sgQ,ffw.shl,ffw.shU,ffw.shX,ffw.shY,ffw.shV,ffw.shW,ffw.shZ})System.out.println(stat+"="+(stat.aKg()&255));
  if(!(eVi.fLJ().pS(1013) instanceof eWx))throw new AssertionError("registry1013");
  for(int mode=0;mode<4;mode++){
   final int coefficient=mode;Map<PC,fff>s=new HashMap<>(),t=new HashMap<>();
   ProbeCombatArithmetic.put(s,ffw.sim,50);ProbeCombatArithmetic.put(t,ffw.sin,20);ProbeCombatArithmetic.put(t,ffw.shQ,10);
   eVn def=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},(p,m,a)->switch(m.getName()){
    case "fKJ"->2;case "aZE"->123456;case "a"->new int[]{100,coefficient}[(int)a[0]];default->throw new UnsupportedOperationException(m.getName());});
   eWx run=new eWx();set(run,Qe.class,"bfp",def);set(run,Qe.class,"bfr",actor(s,0));set(run,Qe.class,"bfs",actor(t,1));
   run.lV(1013);run.dg(902);run.dj(902);run.C(null);
   int expected=new int[]{100,150,120,170}[mode];if(run.getValue()!=expected)throw new AssertionError("mode"+mode+" actual"+run.getValue());
   set(run,eWW.class,"rCB",run.getValue());Method d=eWx.class.getDeclaredMethod("d",PA.class);d.setAccessible(true);d.invoke(run,t.get(ffw.shQ));
   System.out.println("mode"+mode+" value="+run.getValue()+" additional="+HexFormat.of().formatHex(run.bca().QA().toByteArray()));
   Method remove=eWQ.class.getDeclaredMethod("fNM");remove.setAccessible(true);remove.invoke(run);if(t.get(ffw.shQ).aYS()!=10)throw new AssertionError("removal");
  }
  for(byte i=0;i<8;i++){eVg e=eVg.fa(i);if(e!=null)System.out.println("element"+i+" enabled="+e.fLF()+" stat="+(e.fLC()==null?-1:e.fLC().aKg()&255));}
 }
}

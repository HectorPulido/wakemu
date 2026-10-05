import java.lang.reflect.*;import java.util.*;
public class ProbeNativeHPMaximum {
 static void set(Object o,Class<?>c,String n,Object v)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 public static void main(String[]args)throws Exception{
  if(ffw.sgC.aZt()!=-1||!(eVi.fLJ().pS(20) instanceof eWN))throw new AssertionError("registry/cap");
  fff hp=new fff(ffw.sgC,0,1000);hp.or(100);hp.on(60);Map<PC,fff>stats=new HashMap<>();stats.put(ffw.sgC,hp);
  eWN runner=new eWN(ffw.sgC);set(runner,Qe.class,"bfs",ProbeCombatArithmetic.actor(stats,1));set(runner,Qe.class,"aSg",25);set(runner,eWN.class,"rCl",true);set(runner,eWN.class,"rCm",true);
  Method apply=eWN.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);apply.invoke(runner,null,true);
  if(hp.aYU()!=125||hp.aYS()!=85)throw new AssertionError("HP increase");
  runner.bbR();if(hp.aYU()!=100||hp.aYS()!=60)throw new AssertionError("HP restore");
  System.out.println("PASS eVi20=eWNHP,no hardcap;nativeHP60/100->85/125->60/100");
 }
}

import java.lang.reflect.*;import java.util.*;
public class ProbeNativeMinimumResource {
 static void set(Object o,Class<?> c,String n,Object v)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 public static void main(String[]args)throws Exception{
  eWV r=new eWV(ffw.sgC);fff hp=new fff(ffw.sgC,0,100);hp.or(100);hp.on(0);
  Map<PC,fff> stats=new HashMap<>();stats.put(ffw.sgC,hp);
  set(r,Qe.class,"bfs",ProbeCombatArithmetic.actor(stats,1));set(r,Qe.class,"aSg",1);set(r,Qe.class,"bfD",true);
  Method apply=eWV.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);apply.invoke(r,null,true);
  if(hp.aYW()!=1||hp.aYS()!=1||r.getValue()!=1)throw new AssertionError("fresh min");
  r.bbR();if(hp.aYW()!=0||hp.aYS()!=1)throw new AssertionError("remove does not damage");
  set(r,Qe.class,"aSg",150);set(r,Qe.class,"bfD",true);apply.invoke(r,null,true);
  if(hp.aYW()!=100||hp.aYS()!=100||r.getValue()!=100)throw new AssertionError("min clamps rawmax");
  if(GS.C(0.5f)!=1||GS.C(-0.5f)!=0)throw new AssertionError("ceil positive");
  System.out.println("PASS eWV877 native fresh minimum, rawmax clamp, reversible delta, removal preserves HP, GS.C rounding");
 }
}

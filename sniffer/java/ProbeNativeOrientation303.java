import java.lang.reflect.*;
public class ProbeNativeOrientation303 {
 static final class Actor implements InvocationHandler {
  int x,y,d;boolean blocked;Actor(int x,int y,int d){this.x=x;this.y=y;this.d=d;}
  PV proxy(){return (PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},this);}
  public Object invoke(Object p,Method m,Object[] a){
   if(m.getName().equals("bcz"))return x;if(m.getName().equals("bcA"))return y;
   if(m.getName().equals("bcB"))return (short)0;if(m.getName().equals("bcy"))return aAS.wL(d);
   if(m.getName().equals("a")&&a[0] instanceof aAS){d=((aAS)a[0]).wp();return null;}
   if(m.getName().equals("a")&&a[0] instanceof PE)return blocked;
   if(m.getReturnType()==boolean.class)return false;if(m.getReturnType()==int.class)return 0;
   if(m.getReturnType()==long.class)return 0L;return null;
  }
 }
 static final class Runner extends eWF {
  public short fRR(){return 20;}
  void setup(int mode,Actor caster,Actor target){
   bfr=caster.proxy();bfs=target.proxy();bft.w(0,0,0);
   bfp=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->{
    if(m.getName().equals("a")&&m.getReturnType()==int.class)return mode;
    if(m.getReturnType()==boolean.class)return false;return null;});
  }
  void run(){C(null);c(null,false);}
 }
 public static void main(String[]args){
  System.out.println("cannotTurn property="+ffe.sev.aKg());
  for(aAS d:aAS.values())System.out.println("direction "+d+"="+d.wp()+" vec="+d.dyJ+","+d.dyK);
  for(int mode:new int[]{0,1,2,3,4,6,7,8,9,10,11}){
   Actor c=new Actor(0,0,0),t=new Actor(3,1,2);Runner r=new Runner();r.setup(mode,c,t);r.run();
   System.out.println("mode="+mode+" caster="+c.d+" target="+t.d+" value="+r.getValue());
   if(mode==9&&t.d!=5)throw new AssertionError("toward caster expected northwest5");
  }
  Actor c=new Actor(0,0,0),t=new Actor(3,1,0);t.blocked=true;Runner r=new Runner();r.setup(9,c,t);r.run();
  if(t.d!=0)throw new AssertionError("cannotTurn mutated");
  System.out.println("PASS original eWF303 C/c including9 and property guard");
 }
}

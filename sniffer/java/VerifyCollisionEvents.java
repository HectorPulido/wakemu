import java.lang.reflect.*;
public class VerifyCollisionEvents {
 static PV actor(int wp) {
  return (PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->{
   if(m.getName().equals("a")&&a!=null&&a.length==1&&a[0] instanceof PC)return true;
   if(m.getName().equals("c")&&a!=null&&a.length==1&&a[0]==ffw.shF)return wp;
   Class<?> t=m.getReturnType();if(t==boolean.class)return false;if(t==byte.class)return(byte)0;
   if(t==short.class)return(short)1;if(t==int.class)return 0;if(t==long.class)return 1L;
   if(t==float.class)return 0f;if(t==double.class)return 0d;return null;
  });
 }
 static int calculate(int caster,int target)throws Exception {
  eVZ e=eVZ.a(null,ffw.sgD,actor(caster),actor(target));e.b(eVI.fMg());e.ox(2254); System.out.print("before="+e.bbw()+" ");e.C(null);System.out.println("after="+e.bbw());return e.getValue();
 }
 public static void main(String[]args)throws Exception {
  if(calculate(100,0)!=1||calculate(0,100)!=0)throw new AssertionError();
  int zeros=0,ones=0;for(int i=0;i<3;i++){int x=calculate(0,0);if(x==0)zeros++;else if(x==1)ones++;else throw new AssertionError(x);}
  System.out.println("Native eVZ.C: +100willpower=1, target100=0; bare three draws zero="+zeros+" one="+ones);
  iN n=iN.bf(java.util.HexFormat.of().parseHex(args[0]));
  eVZ decoded=new eVZ(ffw.sgD); Method reader=eWW.class.getDeclaredMethod("f",iN.class);reader.setAccessible(true);reader.invoke(decoded,n);
  if(n.QA().LT()!=2||n.QA().Mt()!=0)throw new AssertionError();
  System.out.println("Native iN/eWW.f decoded collision AP AdditionalDatas stat2/origin0");
 }
}

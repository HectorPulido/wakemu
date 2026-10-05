import java.lang.reflect.*;
import java.util.*;
public class ProbeNativeTriggerIdentifiers {
 static void set(Object o,Class<?> c,String n,Object v)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 static long state(Object context){return new eLI(new ArrayList<>()).d(null,null,context,null);}
 static long containerType(Object context){return new eLJ().d(null,null,context,null);}
 static long action(Object context,int depth){ArrayList<alS>args=new ArrayList<>();args.add(new alw(depth));return new eLK(args).d(null,null,context,null);}
 static long identity(Object context,int depth){ArrayList<alS>args=new ArrayList<>();args.add(new alw(depth));return new eLM(args).d(null,null,context,null);}
 static eXE source(int kind,int ref)throws Exception{
  eXE s=new eXE();eVn d=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->switch(m.getName()){case"awM"->kind;case"aZE"->987654;default->throw new UnsupportedOperationException(m.getName());});
  set(s,Qe.class,"bfp",d);if(ref!=0){fyW w=new fyW();set(w,fyW.class,"tyt",(short)ref);set(s,Qe.class,"bfq",w);}return s;
 }
 public static void main(String[]args)throws Exception{
  if(new eLP(new ArrayList<>()).d(null,null,null,null)!=0)throw new AssertionError("nullvalue");
  if(state(null)!=0||action(null,1)!=-1||containerType(null)!=0)throw new AssertionError("no source");
  eXE s=source(400,3442),listener=new eXE();set(listener,Qe.class,"bfu",eVt.a(false,false,s));
  if(state(listener)!=3442||action(listener,1)!=400||action(listener,2)!=400||action(listener,0)!=-1||action(listener,-1)!=-1)throw new AssertionError("fLP/depth");
  if(containerType(listener)!=1)throw new AssertionError("fyW aZY differs from cmZ");
  s.ow(-25);if(new eLP(new ArrayList<>()).d(null,null,listener,null)!=-25)throw new AssertionError("signedvalue");
  if(identity(listener,1)!=987654||identity(listener,2)!=987654||identity(listener,0)!=-1||identity(listener,-1)!=-1||identity(null,1)!=-1)throw new AssertionError("source definitionID/depth");
  eXE other=source(82,0);set(listener,eZR.class,"rIV",other);
  if(state(listener)!=0||action(listener,1)!=82)throw new AssertionError("fSd priority");
  if(containerType(listener)!=0)throw new AssertionError("source null container");
  s=source(400,40000);set(listener,eZR.class,"rIV",s);if(state(listener)!=(short)40000)throw new AssertionError("short");
  System.out.println("PASS native eLI/eLK/eLP/eLM: no-source0/-1, fyW signedshort3442, awM400 not definition987654, fSd precedence, nonpositive depth-1, depth2 same source");
 }
}

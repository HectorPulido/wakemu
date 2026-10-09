import java.lang.reflect.*;
import java.nio.file.*;
import java.util.HexFormat;
/** Native fresh Qe.bca full nullable carry/throw payload differential. */
public class ProbeNativeCarryPayload {
 static void set(Object o,Class<?> c,String n,Object v)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 public static void main(String[]args)throws Exception{
  for(int family:new int[]{333,334}){
   eZR runner=family==333?new eZE():new eWB();
   set(runner,Qe.class,"bfx",1L);set(runner,Qe.class,"bfy",0L);
   set(runner,Qe.class,"bft",new aBn(2,-1,(short)3));set(runner,eZR.class,"rEj",true);
   runner.b((eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->{if(m.getName().equals("aZE"))return 22;throw new AssertionError(m);}));
   PV caster=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->{if(m.getName().equals("Sn"))return 7L;throw new AssertionError(m);});
   set(runner,Qe.class,"bfr",caster);
   if(family==334)set(runner,Qe.class,"bfs",(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->{if(m.getName().equals("Sn"))return -7L;throw new AssertionError(m);}));
   iN original=runner.bca();
   System.out.println(family+" "+HexFormat.of().formatHex(original.toByteArray())+" TIME "+HexFormat.of().formatHex(runner.QH().toByteArray()));
   if(args.length>0){iN candidate=iN.bf(Files.readAllBytes(Path.of(args[0]+family+".bin")));if(!original.equals(candidate))throw new AssertionError("Original native payload differs "+family);}
  }
  System.out.println("PASS original Qe.bca carry/throw nullable identity");
 }
}

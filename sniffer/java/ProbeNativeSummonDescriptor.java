import java.lang.reflect.*;
import java.util.HexFormat;
/** Exercises actual eZl.C and its UID serialization without game/UI/network. */
public class ProbeNativeSummonDescriptor {
 static void set(Object o,String name,Object value)throws Exception {
  for(Class<?> c=o.getClass();c!=null;c=c.getSuperclass())try{
   Field f=c.getDeclaredField(name);f.setAccessible(true);f.set(o,value);return;
  }catch(NoSuchFieldException e){}
  throw new NoSuchFieldException(name);
 }
 static class Runner extends eZl { public short fRR(){return 20;} }
 static Object proxy(Class<?> type,InvocationHandler handler){
  return Proxy.newProxyInstance(type.getClassLoader(),new Class<?>[]{type},handler);
 }
 public static void main(String[]args)throws Exception {
  eGM.a(null);
  System.out.println("eHD inherited property="+eHQ.pSW.aZu()+" "+eHQ.pSW.aYh());
  if(args.length>0){
   cvY message=new cvY();
   if(!message.dp(java.nio.file.Files.readAllBytes(java.nio.file.Path.of(args[0])))
      ||message.d()!=13497||message.awM()!=307||message.cbc()!=99)
    throw new AssertionError("cvY header");
   eZl decoded=new eZl();decoded.lV(307);decoded.ds(message.eIJ());
   if(decoded.LV()!=902||decoded.Qq()!=902||decoded.rHG.fwV()!=901
      ||decoded.rHG.dsr()!=3251||decoded.rHG.cmZ()!=6||!decoded.rHI
      ||decoded.hwX.bhr()!=SR.brt||decoded.hwX.bhs()!=-2
      ||decoded.QH().Pk()!=-1||!decoded.QH().MB())
    throw new AssertionError("Python cvY/eZl decode");
   System.out.println("PASS Python13497 -> actual cvY/eZl complete decode");return;
  }
  int[] p={3251,6,1,3,1,0,-2};
  eVv definition=(eVv)proxy(eVv.class,(o,m,a)->switch(m.getName()) {
   case "aZE" -> 123; case "fKJ" -> p.length; case "a" -> p[(Integer)a[0]];
   default -> throw new UnsupportedOperationException(m.getName());
  });
  PW ids=(PW)proxy(PW.class,(o,m,a)->m.getName().equals("baj")?901L:null);
  PN context=(PN)proxy(PN.class,(o,m,a)->m.getName().equals("bae")?ids:null);
  Runner r=new Runner();set(r,"bfp",definition);set(r,"bfw",context);r.C(null);
  if(r.rHG.dsr()!=3251||r.rHG.cmZ()!=6||r.rHG.fwV()!=901L
    ||r.rHG.bcy().wp()!=3||r.rHG.bcM()!=1||!r.rHI
    ||r.hwX.bhr()!=SR.brt||r.hwX.bhs()!=-2)throw new AssertionError("native descriptor");
  set(r,"bfx",902L);set(r,"bfy",902L);
  set(r,"bfr",ProbeNativeEffectUIDs.actor(7));
  set(r,"bft",new aBn(2,-3,(short)4));
  set(r,"rEj",true);
  r.hwX.ej(7); // Explicit existing caster UID for the binary descriptor fixture.
  iP encoded=iN.QQ();Method write=eZl.class.getDeclaredMethod("a",iP.class);
  write.setAccessible(true);write.invoke(r,encoded);
  Method body=Qe.class.getDeclaredMethod("b",iP.class);body.setAccessible(true);body.invoke(r,encoded);
  iN wire=encoded.QX();if(wire.QK().RD()!=901L)throw new AssertionError("summon UID");
  java.nio.file.Files.write(java.nio.file.Path.of(".runtime/local/native-summon-full.bin"),r.bca().toByteArray());
  set(r,"bfu",eVt.a(true,false,null));
  System.out.println("contextcanonical="+HexFormat.of().formatHex(r.bca().toByteArray()));
  set(r,"bfu",null);
  System.out.println("canonical="+HexFormat.of().formatHex(r.bca().toByteArray()));
  System.out.println("PASS native eZl.C descriptors; AdditionalDatas="+
    HexFormat.of().formatHex(wire.QK().toByteArray())+" full="+HexFormat.of().formatHex(wire.toByteArray())+" blob="+HexFormat.of().formatHex(wire.QA().LO().toByteArray()));
 }
}

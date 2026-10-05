import java.nio.file.*;import java.lang.reflect.*;import java.util.*;
/** Qe/eZR/eYg real owner-container and eVt namespaces. */
public class ProbeNativeRunningContext {
 public static void main(String[]args)throws Exception{
  eGM.a(null);eYg g=new eYg();
  ProbeNativeSummonDescriptor.set(g,"bfp",ProbeNativeEffectUIDs.definition());
  ProbeNativeSummonDescriptor.set(g,"bfr",ProbeNativeEffectUIDs.actor(7));
  ProbeNativeSummonDescriptor.set(g,"bfs",ProbeNativeEffectUIDs.actor(-7));
  ProbeNativeSummonDescriptor.set(g,"bft",new aBn(2,-3,(short)4));
  ProbeNativeSummonDescriptor.set(g,"bfx",901L);ProbeNativeSummonDescriptor.set(g,"bfy",901L);
  PL owner=(PL)Proxy.newProxyInstance(PL.class.getClassLoader(),new Class[]{PL.class},(o,m,a)->switch(m.getName()){
   case "aZY"->11;case "QF"->22L;default->throw new UnsupportedOperationException(m.getName());});
  ProbeNativeSummonDescriptor.set(g,"bfq",owner);
  ProbeNativeSummonDescriptor.set(g,"bfu",eVt.a(true,false,null));
  ProbeNativeSummonDescriptor.set(g,"rEj",true);
  byte[] nativeBody=g.bca().toByteArray();Files.write(Path.of(args[0]),nativeBody);
  System.out.println("native group="+HexFormat.of().formatHex(nativeBody));
  if(args.length>1){
   byte[] python=Files.readAllBytes(Path.of(args[1]));
   if(!Arrays.equals(iN.bf(python).toByteArray(),nativeBody))throw new AssertionError("canonical Qe/eZR namespaces");
   Field spellManager=fyH.class.getDeclaredField("twx");spellManager.setAccessible(true);
   spellManager.set(null,new fyH<fyF>(){public fyG<fyF> j(int reference,short level){return null;}}); // Explicit unavailable fixture owner; context decoder is independent.
   eYg decoded=new eYg();decoded.lV(330);decoded.ds(python);
   if(decoded.LV()!=901||decoded.Qq()!=901||!(decoded.bbf() instanceof eVt)||!((eVt)decoded.bbf()).fLN())throw new AssertionError("eYg context decode");
   System.out.println("PASS Python group -> real eYg/eVt exact canonical namespaces");
  }
 }
}

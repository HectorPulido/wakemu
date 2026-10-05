import java.lang.reflect.*;
import java.nio.file.*;
/** eVi402/eXG cell-only selection, inherited eXE status, native iN decode. */
public class ProbeNativeCellNull {
 static void set(Object o,Class<?> type,String name,Object value)throws Exception{
  Field f=type.getDeclaredField(name);f.setAccessible(true);f.set(o,value);
 }
 public static void main(String[] args)throws Exception{
  org.apache.log4j.BasicConfigurator.configure();Qe.a(()->901L);
  eXG proto=new eXG();
  set(proto,Qe.class,"bfp",(eVv)Proxy.newProxyInstance(eVv.class.getClassLoader(),new Class[]{eVv.class},(p,m,a)->switch(m.getName()){
   case "fKJ"->0;case "aZE"->123;case "aZD"->(byte)2;case "en","eo"->Tt.pz(0);case "aZO"->new java.util.BitSet();default->throw new UnsupportedOperationException(m.getName());}));
  set(proto,Qe.class,"bfr",ProbeNativeEffectUIDs.actor(7));
  set(proto,Qe.class,"bft",new aBn(2,-3,(short)4));
  eXG effect=proto;
  set(effect,Qe.class,"bfx",901L);set(effect,Qe.class,"bfy",901L);
  effect.C(null);
  Method apply=eXE.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);apply.invoke(effect,null,true);
  // eZR.a marks rEj=true after c; avoid unrelated lifecycle/pool finalization.
  set(effect,eZR.class,"rEj",true);
  iN payload=effect.bca();
  if(effect.bbz()||effect.bbA()||!effect.bbB()||effect.QH().Pk()!=-1||!effect.QH().MB())
   throw new AssertionError("Cell null runner contract");
  Files.write(Path.of(args[0]),payload.toByteArray());
  eXG decode=new eXG();decode.lV(402);decode.ds(payload.toByteArray());
  if(decode.LV()!=901||decode.bca().Qq()!=901||decode.bbc()!=null)
   throw new AssertionError("Native cell effect identity/target decode");
  System.out.println("eXG402 target=null,cell(2,-3,4),UID/base901,status-1,executedtrue: PASS");
  if(args.length>1){
   if(!java.util.Arrays.equals(payload.toByteArray(),iN.bf(Files.readAllBytes(Path.of(args[1]))).toByteArray()))
    throw new AssertionError("Canonical Python/native iN byte mismatch");
   eXG python=new eXG();python.lV(402);python.ds(Files.readAllBytes(Path.of(args[1])));
   if(python.LV()!=901||python.bca().Qq()!=901||python.bbc()!=null
       ||python.QH().Pk()!=-1||!python.QH().MB())throw new AssertionError("Python cell null decoder");
   System.out.println("Python cell-null payload -> native eXG decoder PASS");
  }
  Qe.a((Qh)null);
 }
}

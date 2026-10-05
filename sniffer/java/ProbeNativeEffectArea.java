import java.lang.reflect.*;import java.nio.file.*;import java.util.HexFormat;
/** Actual eYQ.C/writer/decoder; area registration is separately audited. */
public class ProbeNativeEffectArea {
 static class Runner extends eYQ{public short fRR(){return 20;}}
 static void set(Object o,String n,Object v)throws Exception{ProbeNativeSummonDescriptor.set(o,n,v);}
 public static void main(String[]args)throws Exception{
  eGM.a(null);int[] p={1546,1,1};
  Runner r=new Runner();
  eVv def=(eVv)Proxy.newProxyInstance(eVv.class.getClassLoader(),new Class[]{eVv.class},(o,m,a)->switch(m.getName()){
   case "aZE"->123;case "fKJ"->p.length;case "a"->p[(Integer)a[0]];default->throw new UnsupportedOperationException(m.getName());});
  PW ids=(PW)Proxy.newProxyInstance(PW.class.getClassLoader(),new Class[]{PW.class},(o,m,a)->901L);
  PN ctx=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(o,m,a)->m.getName().equals("bae")?ids:null);
  set(r,"bfp",def);set(r,"bfw",ctx);set(r,"bfx",902L);set(r,"bfy",902L);
  set(r,"bfr",ProbeNativeEffectUIDs.actor(7));set(r,"bft",new aBn(2,-3,(short)4));
  r.C(null);set(r,"rEj",true);
  byte[] body=r.bca().toByteArray();Files.write(Path.of(args[0]),body);
  if(r.RD()!=901||r.rGR!=1||!r.rGS||r.rGV!=null||r.bbA()||!r.bbB()||r.bbz())throw new AssertionError("eYQ native fields");
  System.out.println("eYQ315area1546 lvl1 keep=true UID901: "+HexFormat.of().formatHex(body));
  if(args.length>1){
   cvY msg=new cvY();msg.dp(Files.readAllBytes(Path.of(args[1])));
   eYQ decoded=new eYQ();decoded.lV(315);decoded.ds(msg.eIJ());
   if(msg.awM()!=315||decoded.RD()!=901||decoded.rGR!=1||!decoded.rGS||decoded.rGV!=null||decoded.LV()!=902)throw new AssertionError("Python native area decode");
   if(!java.util.Arrays.equals(iN.bf(msg.eIJ()).toByteArray(),body))throw new AssertionError("Canonical area bytes differ");
   System.out.println("PASS Python315 cvY/eYQ exact canonical bytes");
  }
 }
}

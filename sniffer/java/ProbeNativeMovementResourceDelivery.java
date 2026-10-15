import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
/**
 * Original aVo completion and aER ordering around native PA hydration.
 * Args: recorded family41 iN payload, maximum MP; optional "AP-loss" uses
 * an explicit native eWR/PC2 operand4, not a claim about a captured Charco.
 * No network, client session, UI interaction or game database is used.
 */
public class ProbeNativeMovementResourceDelivery {
 static void set(Object o,Class<?> c,String n,Object v)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 static class Effects extends eZV {Effects(){super(null);}}
 static class Step extends aET {
  final Runnable operation;
  Step(int sequence,Runnable operation){super(sequence,0,0);this.operation=operation;}
  protected long cby(){operation.run();return 0;}
  protected void cbj(){}
 }
 public static void main(String[] args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  fyZ.guX().a(new bbV());bPS.elL();
  byte[] bytes=Files.readAllBytes(Path.of(args[0]));iN wire=iN.bf(bytes);
  eVn definition=bcA.dcX().AH(wire.Qs());
  int maximum=args.length>1?Integer.parseInt(args[1]):8;
  for(boolean corrected:new boolean[]{false,true}){
  boolean apLoss=args.length>2&&args[2].equals("AP-loss");
  ffw stat=apLoss?ffw.sgD:ffw.sgE;
  fff mp=new fff(stat,0,maximum);mp.or(maximum);mp.on(apLoss?6:3);
  Effects effects=new Effects();
  PV target=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->switch(m.getName()){
   case "Sn"->wire.Qy();case "a"->a[0]==stat;case "b"->mp;case "c"->mp.aYS();case "bax"->effects;
   case "bcz","bcA"->0;case "bcB"->(short)0;case "bcy"->aAS.dyA;case "bav"->(byte)0;
   case "toString"->"NativeMP5Of8";case "hashCode"->System.identityHashCode(p);case "equals"->p==a[0];
   default->throw new UnsupportedOperationException(m.getName());});
  PW actors=(PW)Proxy.newProxyInstance(PW.class.getClassLoader(),new Class[]{PW.class},(p,m,a)->m.getName().equals("de")?target:null);
  PN context=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(p,m,a)->m.getName().equals("bae")?actors:m.invoke(bcz.dcW(),a));
  eZR runner=apLoss?new eWR(ffw.sgD):(eZR)eVi.fLJ().pS(41).bbn();runner.lV(apLoss?37:41);runner.a(context);
  if(apLoss){definition=eVR.j(new float[]{4},1000);set(runner,Qe.class,"aSg",4);}
  else runner.ds(bytes);
  set(runner,Qe.class,"bfp",definition);set(runner,Qe.class,"bfr",target);set(runner,Qe.class,"bfs",target);
  System.out.println("PK="+definition.aZE()+" target="+wire.Qy()+" value="+runner.getValue()+" Ty="+runner.Ty()+" aZN="+runner.aZN());
  aVo action=new aVo(208,517,apLoss?37:41,117,runner,false);
  Method finish=aVo.class.getDeclaredMethod("cYg");finish.setAccessible(true);
  Step hydrate=new Step(corrected?2:1,()->mp.on(apLoss?2:5));
  Step callback=new Step(corrected?1:2,()->{
   try{finish.invoke(action);}catch(Exception error){throw new RuntimeException(error);}
  });
  aER queue=new aER();
  queue.c(corrected?callback:hydrate);queue.c(corrected?hydrate:callback);queue.cbu();
  if(!queue.cbt().isEmpty())throw new AssertionError("Native queue did not drain");
  int expected=corrected?(apLoss?2:5):(apLoss?0:7);
  if(mp.aYS()!=expected)throw new AssertionError("Native ordered result "+mp.aYS()+" expected "+expected);
  System.out.println("PASS "+(corrected?"callback_then_final_snapshot":"final_snapshot_then_callback")+" stat="+(stat.aKg()&255)+" final="+mp.aYS()+" bbs="+runner.bbs());
  }
 }
}

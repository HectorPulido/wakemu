import java.nio.file.*;import java.lang.reflect.*;
import com.google.protobuf.Descriptors;
/** Real aTR/aVo/Qf and UI model; recorded payload with explicit native PL1 control. */
public final class ProbeNativeStateChildDelivery {
 static class Complete extends aVo {
  final buQ world;
  Complete(eZR r,PV caster,PV target){super(1,0,r.d(),7,r,false);
   PW actors=(PW)Proxy.newProxyInstance(PW.class.getClassLoader(),new Class[]{PW.class},(p,m,a)->m.getName().equals("de")?(((Long)a[0])==caster.Sn()?caster:((Long)a[0])==target.Sn()?target:null):null);
   PN context=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(p,m,a)->m.getName().equals("bae")?actors:m.invoke(bcz.dcW(),a));
   world=(buQ)Proxy.newProxyInstance(buQ.class.getClassLoader(),new Class[]{buQ.class},(p,m,a)->switch(m.getName()){case "bbg"->context;case "equals"->p==a[0];default->null;});
  }protected buQ cjD(){return world;}
 }
 static class Observe extends aTR {Observe(eZR r){super(1,0,7,r.d(),r);}void execute(){super.cbj();}}
 static void set(Object obj,Class<?> cls,String field,Object v)throws Exception{Field f=cls.getDeclaredField(field);f.setAccessible(true);f.set(obj,v);}
 static int count(Qf manager){int n=0;for(var it=manager.iterator();it.hasNext();){it.next();n++;}return n;}
 public static void main(String[] args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");fyZ.guX().a(new bbV());
  for(int cls:new int[]{330,400}){
   iN original=iN.bf(Files.readAllBytes(Path.of(args[cls==330?0:1])));
   boolean recorded=args.length>2&&args[2].equals("--recorded-pl");
   short reference=recorded?(short)(original.QF()>>>16):(short)(cls==330?8913:3442),level=recorded?(short)original.QF():(short)(cls==330?30:10);
   fyW state=fyZ.guX().aax(reference).cu(level);
   var builder=original.QR();builder.eM(1);builder.ao(state.QF());
   byte[] controlled=recorded?original.toByteArray():builder.QX().toByteArray();
   if(recorded&&state.QF()!=original.QF())throw new AssertionError("recorded PL was not resolved exactly");
   System.out.println("PL reference="+reference+" level="+level+" recorded="+recorded);
   for(boolean complete:new boolean[]{false,true}){
    var cm=new ProbeNativeStateManager.Collection();var tm=new ProbeNativeStateManager.Collection();
    PV caster=ProbeNativeStateManager.actor(original.Qw(),cm),target=original.Qw()==original.Qy()?caster:ProbeNativeStateManager.actor(original.Qy(),tm);
    eZR runner=cls==330?new eYg():new eXE();runner.lV(cls);runner.a(bcz.dcW());
    if(runner.ds(controlled)==null)throw new AssertionError("decode failed");
    eVn definition=null;for(eVn e:state.guJ())if(e.aZE()==original.Qs())definition=e;
    if(definition==null)throw new AssertionError("wrong definition");
    set(runner,Qe.class,"bfp",definition);set(runner,Qe.class,"bfr",caster);set(runner,Qe.class,"bfs",target);
    if(!(runner.bbe() instanceof fyW)||runner.bbe().QF()!=state.QF())throw new AssertionError("native PL1 resolution");
    System.out.println("before class="+cls+" route="+(complete?12613:13497)+" Ty="+runner.Ty()+" aZN="+runner.aZN()+" bbW="+runner.bbW()+" bbs="+runner.bbs()+" value="+runner.getValue());
    if(complete){Complete action=new Complete(runner,caster,target);action.cYb();action.fe(target.Sn());action.iD(caster.Sn());aER queue=new aER();queue.c(action);queue.cbu();if(!queue.cbt().isEmpty())throw new AssertionError("queue not drained");}
    else {runner.bbq();new Observe(runner).execute();}
    int retained=count(cm)+count(tm);bPE display=new bPG().c(runner,-1);
    int expected=cls==330||complete?1:0;
    if(retained!=expected || (display==null?0:display.elp())!=expected)throw new AssertionError("delivery/UI registration mismatch");
    if(complete && runner.bbs())throw new AssertionError("client gameplay still enabled");
    System.out.println("after class="+cls+" route="+(complete?12613:13497)+" retained="+retained+" display="+(display==null?0:display.elp())+" bbs="+runner.bbs());
   }
  }
  System.out.println("PASS: original330/400 observation versus completion, realQf andUIcontainer");
 }
}

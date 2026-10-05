import java.nio.file.*;import java.lang.reflect.*;
/** Original official payloads, unchanged; original Qf and aTR/aVo completion. */
public final class ProbeOfficialStatDelivery {
 static Qe prototype(int family)throws Exception{for(Field f:eVi.class.getDeclaredFields())if(f.getType()==eVj.class&&Modifier.isStatic(f.getModifiers())){f.setAccessible(true);eVj r=(eVj)f.get(null);if(r.d()==family)return (Qe)r.bkv();}throw new AssertionError("registry");}
 public static void main(String[] args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");fyZ.guX().a(new bbV());bPS.elL();
  for(int family:new int[]{193,649}){
   byte[] bytes=Files.readAllBytes(Path.of(args[family==193?0:1]));iN wire=iN.bf(bytes);
   eVn definition=bcA.dcX().AH(wire.Qs());if(definition.awM()!=family)throw new AssertionError("official PK family mismatch");
   for(boolean completion:new boolean[]{false,true}){
    var cm=new ProbeNativeStateManager.Collection();var tm=new ProbeNativeStateManager.Collection();
    PV caster=ProbeNativeStateManager.actor(wire.Qw(),cm),target=wire.Qw()==wire.Qy()?caster:ProbeNativeStateManager.actor(wire.Qy(),tm);
    if(family==649){bjo player=new bjo();player.dA(wire.Qy());ProbeNativeStateChildDelivery.set(player,bjo.class,"ikM",new bPN(player));ProbeNativeStateChildDelivery.set(player,eGj.class,"pGG",tm);target=player;if(wire.Qw()==wire.Qy())caster=player;if(player.dok()==null)throw new AssertionError("native player spell manager missing");}
    final PV resolvedCaster=caster,resolvedTarget=target;
    PW actors=(PW)Proxy.newProxyInstance(PW.class.getClassLoader(),new Class[]{PW.class},(p,m,a)->m.getName().equals("de")?(((Long)a[0])==resolvedCaster.Sn()?resolvedCaster:((Long)a[0])==resolvedTarget.Sn()?resolvedTarget:null):null);
    PN context=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(p,m,a)->m.getName().equals("bae")?actors:m.invoke(bcz.dcW(),a));
    eZR runner=(eZR)prototype(family).bbn();runner.lV(family);runner.a(context);
    if(runner.ds(bytes)==null)throw new AssertionError("original decode");
    ProbeNativeStateChildDelivery.set(runner,Qe.class,"bfp",definition);ProbeNativeStateChildDelivery.set(runner,Qe.class,"bfr",caster);ProbeNativeStateChildDelivery.set(runner,Qe.class,"bfs",target);
    boolean ty=runner.Ty(),azn=runner.aZN(),bw=runner.bbW();
    System.out.println("before family="+family+" PK="+wire.Qs()+" PL="+wire.QD()+"/"+wire.QF()+" resolved="+(runner.bbe()==null?"null":runner.bbe().getClass().getName())+" route="+(completion?12613:13497)+" Ty="+ty+" aZN="+azn+" bbW="+bw+" value="+runner.getValue());
    if(completion){var action=new ProbeNativeStateChildDelivery.Complete(runner,caster,target);action.cYb();action.fe(target.Sn());action.iD(caster.Sn());var queue=new aER();queue.c(action);queue.cbu();if(!queue.cbt().isEmpty())throw new AssertionError("queue");}
    else{runner.bbq();new ProbeNativeStateChildDelivery.Observe(runner).execute();}
    int retained=ProbeNativeStateChildDelivery.count(caster.bax())+(caster==target?0:ProbeNativeStateChildDelivery.count(target.bax()));
    int expected=completion?(ty?1:0):((ty||bw)&&(azn||bw)?1:0);
    if(retained!=expected)throw new AssertionError("Qf expected "+expected+" got "+retained);
    System.out.println("after family="+family+" route="+(completion?12613:13497)+" retained="+retained+" bbs="+runner.bbs());
   }
  }
  System.out.println("PASS original official193/649 payload registration guards");
 }
}

import java.lang.reflect.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import java.lang.reflect.Proxy;

/** Isolated headless proof of actual opcode13726 cvE -> cjp -> aTW on bcT ref207. */
public class ProbeNativeAreaDeathRemoval {
  static final int FIGHT=7731, ACTION=4, SEQUENCE=5;
  static final long BAG_UID=99001, FOREIGN_UID=99002;
  static class Manager extends Qs { public Qq dp(long uid){return null;} }
  static class HeadlessActorWrapper extends YF { public void bpI(){} }
  static Object zero(Class<?> c){if(c==boolean.class)return false;if(c==int.class)return 0;if(c==long.class)return 0L;if(c==short.class)return(short)0;if(c==byte.class)return(byte)0;return null;}
  static void set(Object o,String n,Object v)throws Exception{for(Class<?>c=o.getClass();c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);return;}catch(NoSuchFieldException ignored){}throw new NoSuchFieldException(n);}
  @SuppressWarnings("unchecked") static <T>T get(Object o,String n)throws Exception{for(Class<?>c=o.getClass();c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(n);f.setAccessible(true);return(T)f.get(o);}catch(NoSuchFieldException ignored){}throw new NoSuchFieldException(n);}
  static faV prototype(int ref)throws Exception{
    apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
    final faV[] found={null};
    apw.bGL().a(new aKa(),new apB<aKa>(){public void load(aKa a){if(a.d()==ref)found[0]=bcN.hFx.a(a);}});
    if(found[0]==null)throw new AssertionError("missing faV prototype "+ref); return found[0];
  }
  public static void main(String[] args)throws Exception{
    org.apache.log4j.BasicConfigurator.configure(); eGM.a(null);
    faV q=prototype(207).b(new fbm(BAG_UID,2,-3,(short)4,null,(byte)-1,null,(short)1,aAS.wL(3)));
    if(!(q instanceof bcT)||!(q instanceof bdk))throw new AssertionError("ref207 factory did not produce bdk bcT: "+q.getClass());
    faV foreign=prototype(207).b(new fbm(FOREIGN_UID,9,11,(short)4,null,(byte)-1,null,(short)1,aAS.wL(3)));
    Manager manager=new Manager(); QI qi=new QI(); aJG visuals=aJG.cjB(); visuals.clear();
    Map<Qq,Ze> areaWrappers=get(visuals,"efb"); areaWrappers.put(q,null);areaWrappers.put(foreign,null);
    Map<Qq,YF> actorWrappers=get(visuals,"efc");
    HeadlessActorWrapper actor=(HeadlessActorWrapper)unsafeAllocate(HeadlessActorWrapper.class);set(actor,"aHm",BAG_UID);actorWrappers.put(q,actor);
    HeadlessActorWrapper foreignActor=(HeadlessActorWrapper)unsafeAllocate(HeadlessActorWrapper.class);set(foreignActor,"aHm",FOREIGN_UID);actorWrappers.put(foreign,foreignActor);
    YP actorRegistry=YP.bqw();Map<Long,YF> liveActors=get(actorRegistry,"bUL");liveActors.put(BAG_UID,actor);liveActors.put(FOREIGN_UID,foreignActor);
    manager.a((Qu)Proxy.newProxyInstance(Qu.class.getClassLoader(),new Class[]{Qu.class},(o,m,a)->{
      if(m.getName().equals("f")){qi.f((QK)a[0]);return null;}
      if(m.getName().equals("g")){qi.g((QK)a[0]);visuals.o((Qq)a[0]);return null;}
      return zero(m.getReturnType());
    }));
    manager.a(q);manager.a(foreign);
    if(manager.dn(BAG_UID)!=q||manager.dn(FOREIGN_UID)!=foreign||!areaWrappers.containsKey(q)||!areaWrappers.containsKey(foreign)||!actorWrappers.containsKey(q)||!actorWrappers.containsKey(foreign)||!liveActors.containsKey(BAG_UID)||!liveActors.containsKey(FOREIGN_UID))throw new AssertionError("bag setup failed");
    // Prevent the process-global UI actor manager from treating a null death wrapper as its live selection.
    ddQ scene=ddQ.fgY();set(scene,"osN",Proxy.newProxyInstance(VU.class.getClassLoader(),new Class[]{VU.class},(o,m,a)->zero(m.getReturnType())));
    PN nativeContext=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(o,m,a)->m.getName().equals("baf")?manager:zero(m.getReturnType()));
    buS fights=buS.dMq();Field mapField=buS.class.getDeclaredField("jrq");mapField.setAccessible(true);Object fightMap=mapField.get(fights);
    buQ context=(buQ)Proxy.newProxyInstance(buQ.class.getClassLoader(),new Class[]{buQ.class},(o,m,a)->switch(m.getName()){
      case "d"->FIGHT;case "baf"->manager;case "bbg"->nativeContext;default->zero(m.getReturnType());
    });
    fightMap.getClass().getMethod("put",int.class,Object.class).invoke(fightMap,FIGHT,context);
    byte[] frame=ByteBuffer.allocate(20).putInt(FIGHT).putInt(ACTION).putInt(SEQUENCE).putLong(BAG_UID).array();
    cvE packet=new cvE();if(!packet.dp(frame)||packet.d()!=13726||packet.eIj()!=BAG_UID)throw new AssertionError("cvE 13726 parse");
    new cjp().a(packet); // Actual native opcode handler constructs/registers aTW.
    Method lookup=aUb.class.getDeclaredMethod("Ad",int.class);lookup.setAccessible(true);aER group=(aER)lookup.invoke(aUb.cXs(),FIGHT);
    aEO pending=group.cbs();if(pending==null)throw new AssertionError("cjp did not enqueue aTW");
    List<?> actions=pending.cbn();aTW death=actions.stream().filter(aTW.class::isInstance).map(aTW.class::cast).findFirst().orElseThrow(()->new AssertionError("aTW not enqueued"));
    death.run(); // Exercise native timer's zero-delay death callback.
    byte[] repeatFrame=ByteBuffer.allocate(20).putInt(FIGHT).putInt(ACTION+1).putInt(SEQUENCE+1).putLong(BAG_UID).array();
    cvE repeatedPacket=new cvE();if(!repeatedPacket.dp(repeatFrame))throw new AssertionError("repeat cvE parse");
    new cjp().a(repeatedPacket);
    List<?> repeatedActions=group.cbs().cbn();
    aTW repeat=repeatedActions.stream().filter(aTW.class::isInstance).map(aTW.class::cast).filter(a->a!=death).findFirst().orElseThrow(()->new AssertionError("repeat aTW not enqueued"));
    repeat.run(); // Missing area UID is an idempotent native no-op.
    if(manager.dn(BAG_UID)!=null||areaWrappers.containsKey(q)||actorWrappers.containsKey(q)||liveActors.containsKey(BAG_UID)||manager.dn(FOREIGN_UID)!=foreign||!areaWrappers.containsKey(foreign)||!actorWrappers.containsKey(foreign)||!liveActors.containsKey(FOREIGN_UID)){System.out.println("bag manager="+manager.dn(BAG_UID)+" area="+areaWrappers.containsKey(q)+" actor="+actorWrappers.containsKey(q)+" registry="+liveActors.containsKey(BAG_UID)+"; foreign manager="+(manager.dn(FOREIGN_UID)==foreign)+" area="+areaWrappers.containsKey(foreign)+" actor="+actorWrappers.containsKey(foreign)+" registry="+liveActors.containsKey(FOREIGN_UID));throw new AssertionError("aTW failed native bcT Qs/aJG removal");}
    System.out.println("PASS opcode13726 cvE->cjp->aTW removes only actual factory bcT bag ref207 UID="+BAG_UID+" from Qs, aJG wrappers and YP; repeat UID was a no-op; bcT.bcN=-1 means no QI obstacle slot; foreign bcT UID="+FOREIGN_UID+" remains (headless; no rendered proof)");
    System.exit(0);
  }
  static Object unsafeAllocate(Class<?> type)throws Exception{Field f=Class.forName("sun.misc.Unsafe").getDeclaredField("theUnsafe");f.setAccessible(true);return((sun.misc.Unsafe)f.get(null)).allocateInstance(type);}
}

import java.lang.reflect.*;
import java.util.*;

/** Executes native Qs removal and aJG wrapper cleanup without initializing render resources. */
public class ProbeNativeAreaManagerRemoval {
  static final class Manager extends Qs { public Qq dp(long uid) { return null; } }
  static void set(Object o, String name, Object value) throws Exception {
    for (Class<?> c=o.getClass(); c!=null; c=c.getSuperclass()) {
      try { Field f=c.getDeclaredField(name); f.setAccessible(true); f.set(o,value); return; }
      catch (NoSuchFieldException ignored) {}
    }
    throw new NoSuchFieldException(name);
  }
  @SuppressWarnings("unchecked") static <T> T get(Object o, String name) throws Exception {
    for (Class<?> c=o.getClass(); c!=null; c=c.getSuperclass()) {
      try { Field f=c.getDeclaredField(name); f.setAccessible(true); return (T)f.get(o); }
      catch (NoSuchFieldException ignored) {}
    }
    throw new NoSuchFieldException(name);
  }
  static final class HeadlessActorWrapper extends YF { public void bpI() {} }
  static final class TrapRunner extends eYW { boolean executed; public boolean Ty() { return executed; } }
  static Object unsafeAllocate(Class<?> type) throws Exception {
    Field f=Class.forName("sun.misc.Unsafe").getDeclaredField("theUnsafe"); f.setAccessible(true);
    return ((sun.misc.Unsafe)f.get(null)).allocateInstance(type);
  }
  static faV prototype(int ref) throws Exception {
    apw.bGL().dd("jar:file:"+java.nio.file.Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
    final faV[] found={null};
    apw.bGL().a(new aKa(),new apB<aKa>() { public void load(aKa a) { if(a.d()==ref) found[0]=bcN.hFx.a(a); } });
    if(found[0]==null) throw new AssertionError("missing native Qq prototype "+ref);
    return found[0];
  }
  static faV area(faV prototype,long uid) throws Exception {
    faV q=prototype.b(new fbm(uid,2,-3,(short)4,null,(byte)-1,null,(short)1,aAS.wL(3)));
    if(q.Sn()!=uid) throw new AssertionError("native Qq UID");
    return q;
  }
  public static void main(String[] args) throws Exception {
    eGM.a(null);
    Manager manager=new Manager(); faV glyph=area(prototype(910),7001); Qq q=glyph;
    if(!(q instanceof faY)||q.bcN()!=-1) throw new AssertionError("native faY area must carry non-actor slot -1");
    QI qi=new QI(); aJG visuals=aJG.cjB(); visuals.clear();
    Map<Qq,Ze> areaWrappers=get(visuals,"efb"); areaWrappers.put(q,null);
    Map<Qq,YF> actorWrappers=get(visuals,"efc");
    HeadlessActorWrapper actor=(HeadlessActorWrapper)unsafeAllocate(HeadlessActorWrapper.class); set(actor,"aHm",7001L);
    actorWrappers.put(q,actor);
    YP actorRegistry=YP.bqw(); Map<Long,YF> liveActors=get(actorRegistry,"bUL"); liveActors.put(7001L,actor);
    manager.a((Qu)Proxy.newProxyInstance(Qu.class.getClassLoader(),new Class[]{Qu.class},(o,m,a)->{
      if(m.getName().equals("f")){ qi.f((QK)a[0]); return null; }
      if(m.getName().equals("g")){ qi.g((QK)a[0]); visuals.o((Qq)a[0]); return null; }
      if(m.getReturnType()==void.class)return null;
      if(m.getReturnType()==boolean.class)return false;
      if(m.getReturnType()==int.class)return 0;
      if(m.getReturnType()==long.class)return 0L;
      return null;
    }));
    manager.a(q);
    if(manager.bdl()!=1||manager.dm(7001)!=q||!areaWrappers.containsKey(q)||!actorWrappers.containsKey(q)||!liveActors.containsKey(7001L)||Arrays.stream(qi.bdI()).anyMatch(x->x==q))
      throw new AssertionError("native Qs/aJG add setup");
    manager.b(q);
    if(manager.bdl()!=0||manager.dn(7001)!=null||areaWrappers.containsKey(q)||actorWrappers.containsKey(q)||liveActors.containsKey(7001L)||Arrays.stream(qi.bdI()).anyMatch(x->x==q))
      throw new AssertionError("native Qs occupancy/aJG wrapper removal");
    // Family 308's retained-area callback is eYQ.bbR inherited by eYW.
    for (boolean keep:new boolean[]{false,true}) for(boolean executed:new boolean[]{false,true}) {
      long uid=7010+(keep?2:0)+(executed?1:0);
      Qq trap=area(prototype(1474),uid);
      if(!(trap instanceof faY)||trap.bcN()!=-1) throw new AssertionError("native retained trap must be non-actor faY");
      manager.a(trap);
      areaWrappers.put(trap,null);
      HeadlessActorWrapper trapVisual=(HeadlessActorWrapper)unsafeAllocate(HeadlessActorWrapper.class);
      set(trapVisual,"aHm",uid); actorWrappers.put(trap,trapVisual); liveActors.put(uid,trapVisual);
      TrapRunner runner=new TrapRunner(); runner.executed=executed;
      set(runner,"bfw",Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(o,m,a)->
        m.getName().equals("baf")?manager:null));
      set(runner,"oAP",trap); set(runner,"rGS",keep); runner.bbR();
      boolean shouldRemove=!keep&&executed;
      if((manager.dn(uid)==null)!=shouldRemove || areaWrappers.containsKey(trap)==shouldRemove
         ||actorWrappers.containsKey(trap)==shouldRemove||liveActors.containsKey(uid)==shouldRemove
         ||Arrays.stream(qi.bdI()).anyMatch(x->x==trap))
        throw new AssertionError("family308 native keep/executed removal uid="+uid);
      if(!shouldRemove) { manager.b(trap); }
    }
    System.out.println("PASS native faY910 Qs/aJG cleanup and family308 eYW/eYQ.bbR retained-trap matrix; headless actor wrapper registry detached");
  }
}

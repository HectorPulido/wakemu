import java.lang.reflect.*;
import java.util.*;
import java.nio.*;

/** Offline original-JAR witness; no client class rewriting or runtime patch. */
public final class ProbeNativeGrantPhaseLifecycle {
 static int checks;
 static void check(boolean ok,String label){if(!ok)throw new AssertionError(label);checks++;}
 static void set(Object o,Class<?> c,String n,Object v)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 static Object allocate(Class<?> c)throws Exception{Field f=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);return ((sun.misc.Unsafe)f.get(null)).allocateInstance(c);}
 static class Spell extends fyG<fyF> {
  public long LV(){return 4604L;}public int awe(){return 4604;}public int bwX(){return 1;}
  public fyH<fyF> elD(){return null;} public Rq bfj(){return this;} public Rq bfk(){return this;}
  public boolean a(yy ignored){return false;} public boolean b(yy ignored){return false;}
 }
 static class Manager extends bOY {
  bOX bar;
  public bOX c(fyv kind,byte index){return kind==fyv.tuO&&index==2?bar:null;}
 }
 static class Actor extends biB {
  fyR book;fzf registry;eZV effects;boolean controlled=true;
  Actor(){super(false);}
  public fyR dok(){return book;} public fzf drs(){return registry;}
  public long Sn(){return 16L;} public boolean doz(){return controlled;}
  public boolean baw(){return true;} public eZV drJ(){return effects;} public Qf bax(){return effects;} public bPo drI(){return null;}
 }
 static class Fight extends buH {
  Actor actor;long owner=17L;bvY timeline;
  Fight(){super(1,null,null,null,null,null);}
  public Collection<big> dLy(){return List.of(actor);}
  public long bhJ(){return owner;}
  public int d(){return 1;}
  public fj[] zj(){return new fj[]{new fcc(this)};}
  public SU bac(){return timeline;}
  public bvY dLW(){return timeline;}
  public PN bbg(){return(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(o,m,a)->null);}
  public big ku(long id){return actor!=null&&actor.Sn()==id?actor:null;}
 }
 static class Hooks extends SZ {
  protected void a(SX x){}protected void b(SX x){}protected void c(SX x){}
  protected void a(SX x,long id){}protected void a(SX x,long id,int n){}
  protected void b(SX x,long id,int n){}
 }
 static class Screen extends Zi {
  public boolean a(java.awt.event.MouseEvent e){return false;}public boolean b(java.awt.event.MouseEvent e){return false;}
  public boolean c(java.awt.event.MouseEvent e){return false;}public boolean d(java.awt.event.MouseEvent e){return false;}
  public boolean e(java.awt.event.MouseEvent e){return false;}public boolean a(java.awt.event.MouseWheelEvent e){return false;}
  public boolean a(java.awt.event.KeyEvent e){return false;}public boolean b(java.awt.event.KeyEvent e){return false;}
  public boolean c(java.awt.event.KeyEvent e){return false;}public boolean a(java.awt.event.FocusEvent e){return false;}
  public boolean b(java.awt.event.FocusEvent e){return false;}protected Zi a(aqM ignored){return this;}
 }
 static void ongoingRecovery(Fight fight,Actor actor,Manager manager,eWn runner)throws Exception{
  Screen screen=(Screen)allocate(Screen.class);Zf camera=(Zf)allocate(Zf.class);
  set(camera,afe.class,"cqI",new afG());set(screen,aeU.class,"cpQ",camera);agO.bBj().g(screen);
  fev stats=(fev)Proxy.newProxyInstance(fev.class.getClassLoader(),new Class[]{fev.class},(o,m,a)->m.getName().equals("rI")?false:0);
  fight.timeline=new bvY(fight,new feN(),stats,new Hooks(),new Tc(null));
  set(actor,big.class,"igF",allocate(bkO.class));
  buX controller=(buX)allocate(buX.class);set(controller,buX.class,"jsd",actor);set(controller,buX.class,"jse",fight.timeline);actor.a(controller);
  fight.a(fbZ.ff((byte)2));
  fyS usage=new fyS();usage.gur().put(4604,2);usage.gus().put(4604,5);usage.gut().put(987654321L,1);usage.guu().put((byte)2,3);
  set(actor,eGj.class,"pGC",Proxy.newProxyInstance(eGZ.class.getClassLoader(),new Class[]{eGZ.class},(o,m,a)->m.getName().equals("fqI")?usage:null));
  byte[] castHistory=actor.fqI().aqv();
  Object book=actor.book.dL(4604L);Object shortcut=manager.bar.lY(4604L);
  ByteBuffer state=ByteBuffer.allocate(54);
  state.putShort((short)3).putInt(17).put((byte)1).putLong(999999L);
  state.put((byte)1).putLong(actor.Sn()).put((byte)1).putLong(actor.Sn());
  state.put((byte)1).putLong(actor.Sn()).putShort((short)4).put((byte)0);
  state.put((byte)0).put((byte)0);
  byte[] timeline=Arrays.copyOf(state.array(),state.position());
  ByteBuffer envelope=ByteBuffer.allocate(9+timeline.length);
  envelope.put((byte)1).put((byte)0).putInt(6).put((byte)0).putShort((short)timeline.length).put(timeline);
  ByteBuffer body=ByteBuffer.allocate(6+envelope.capacity());body.putInt(1).putShort((short)envelope.capacity()).put(envelope.array());
  cvn message=new cvn();check(message.dp(body.array()),"original cvn decoder accepts full recovery");
  cjv recoveryConsumer=new cjv();set(recoveryConsumer,cjm.class,"jsz",fight);recoveryConsumer.a(message);
  check(fight.dLv()==fbZ.ff((byte)2),"actual12053 recovery retains ACTION phase");
  check(fight.timeline.bhp(),"actual12053 starts restored native timeline");
  check(fight.timeline.bhJ()==actor.Sn(),"actual12053 restores current actor");
  check(actor.dnD()==controller&&controller.dLW()==fight.timeline,"actual12053 retains original controller attachment");
  check(actor.book.dL(4604L)==book&&runner.fMS()==book,"actual12053 preserves granted spell object");
  check(manager.bar.lY(4604L)==shortcut&&manager.bar.a((bOS)shortcut)==3,"actual12053 preserves moved shortcut identity and slot");
  check(actor.effects.dk(runner.LV())==runner,"actual12053 preserves retained649 identity");
  check(actor.fqI()==usage&&Arrays.equals(actor.fqI().aqv(),castHistory),"actual12053 preserves nativefyS usage and interval/target counters");
 }
 static eWn grant(Actor actor,boolean executed)throws Exception{
  eWn r=new eWn();r.f(actor);r.dg(987654L);r.lV(649);
  set(r,eWn.class,"hXV",4604);set(r,eWn.class,"rAY",new Spell());
  set(r,eWn.class,"rAX",(short)1);set(r,eWn.class,"rAV",(byte)2);set(r,eWn.class,"rAW",(short)4);
  set(r,eZR.class,"rEj",executed);set(r,eZR.class,"rIX",new Ts(100L,(short)1,false));
  return r;
 }
 public static void main(String[] args)throws Exception{
  org.apache.log4j.BasicConfigurator.configure();
  Actor a=(Actor)allocate(Actor.class);a.controlled=true;
  a.book=new fyR((short)100,null,null,false,false,false);a.registry=new fzf();a.effects=new eZV(a);
  Manager manager=(Manager)allocate(Manager.class);manager.bar=new bOX(fyv.tuO,(byte)2);set(a,biB.class,"iig",manager);
  Fight fight=(Fight)allocate(Fight.class);fight.actor=a;fight.owner=17L;
  ckv consumer=new ckv();set(consumer,cjm.class,"jsz",fight);
  Method phase=ckv.class.getDeclaredMethod("eDR");phase.setAccessible(true);
  phase.invoke(consumer);
  check(a.book.dL(4604L)==null&&manager.bar.lY(4604L)==null,"initial native phase before649 leaves grant bar empty");
  eWn old=grant(a,true);set(a.effects,Qf.class,"bfT",new HashMap<Long,Qe>(Map.of(old.LV(),old)));old.fMO();
  check(a.book.dL(4604L)!=null,"original fMO creates raw granted book UID");
  check(a.registry.aaB(4604),"original fMO creates execution registry entry");
  Object shortcut=manager.bar.lY(4604L);
  check(shortcut!=null,"original biB.a creates shortcut");
  check(manager.bar.a((bOS)shortcut)==4,"original shortcut slot4");
  long originalRunnerUID=old.LV();
  fyG originalBookObject=old.fMS();
  manager.bar.c((bOS)shortcut);shortcut=bOS.a(fyw.tvb,4604L,4604,1);manager.bar.a((bOS)shortcut,(short)3);set(old,eWn.class,"rAZ",shortcut);
  check(manager.bar.a((bOS)shortcut)==3,"user moves native shortcut from configured4 to3");
  ongoingRecovery(fight,a,manager,old);
  check(a.effects.q(old),"original Qf.q removes old runner");
  check(a.book.dL(4604L)==null,"removal clears book");
  check(!a.registry.aaB(4604),"removal clears execution registry");
  check(manager.bar.lY(4604L)==null,"removal clears shortcut");
  phase.invoke(consumer);
  check(a.book.dL(4604L)==null,"original phase does not recreate removed grant");
  eWn replacement=grant(a,true);set(a.effects,Qf.class,"bfT",new HashMap<Long,Qe>(Map.of(replacement.LV(),replacement)));replacement.fMO();
  check(replacement.LV()==originalRunnerUID,"same runner UID on recreation");
  check(a.book.dL(4604L)==replacement.fMS(),"replacement object is installed in the book");
  check(manager.bar.a((bOS)manager.bar.lY(4604L))==4,"same bar and slot on recreation");
  check(replacement.fMS()!=originalBookObject,"recreation replaces dynamic granted book object");
  check(manager.bar.a((bOS)manager.bar.lY(4604L))!=3,"recreation loses user moved slot3");
  a.controlled=false;phase.invoke(consumer);
  check(a.book.dL(4604L)==replacement.fMS(),"noncontrolled phase does not replace active grant object");
  check(manager.bar.a(manager.bar.lY(4604L))==4,"noncontrolled phase leaves existing shortcut slot intact");
  a.controlled=true;
  check(a.effects.q(replacement),"replacement is removable");
  check(a.book.dL(4604L)==null&&manager.bar.lY(4604L)==null,"final cleanup removes recreated book and shortcut");
  System.out.println("PASS "+checks+" original grant cleanup / phase / recreation / final cleanup checks; recreation replaces book identity and loses user moved slot");
 }
}

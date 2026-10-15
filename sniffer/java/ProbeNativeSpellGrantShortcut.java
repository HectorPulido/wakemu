import java.lang.reflect.*;
/** Isolated native shortcut inventory and precise temporary-grant helper checks. */
public class ProbeNativeSpellGrantShortcut {
 static Object allocate(Class<?> type)throws Exception{Field f=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);return ((sun.misc.Unsafe)f.get(null)).allocateInstance(type);}
 static class Spell extends fyG<fyF> {
  long uid;int reference,value;
  public long LV(){return uid;}public int awe(){return reference;}public int bwX(){return value;}
  public fyH<fyF> elD(){return null;}
  public Rq bfj(){return this;} public Rq bfk(){return this;}
  public boolean b(yy ignored){return false;}
  public boolean a(yy ignored){return false;}
 }
 static class Manager extends bOY {
  bOX bar;
  public bOX c(fyv kind,byte index){return bar!=null&&kind==fyv.tuO&&index==2?bar:null;}
 }
 static class Fight extends buH {
  Actor actor;boolean registered=true;
  Fight(){super(1,null,null,null,null,null);}
  public big rj(long id){return registered&&actor!=null&&id==actor.Sn()?actor:null;}
 }
 static class Actor extends biB {
  Manager manager;Fight fight;int calls;boolean controlled=true;
  fyR book; fzf registry;
  Actor(){super(false);}
  public boolean doz(){return controlled;} public fcb dpt(){return fight;}
  public bOY dpp(){return manager;} public long Sn(){return 16;}
  public eZV bax(){return null;}
  public bPo drI(){return null;}
  public fyR dok(){return book;} public fzf drs(){return registry;}
  public fyt a(byte index,short slot,fyG spell){calls++;return null;}
 }
 static void check(boolean condition,String reason){if(!condition)throw new AssertionError(reason);}
 public static void main(String[]args)throws Exception{
  bOX bar=new bOX(fyv.tuO,(byte)2);
  bOS shortcut=bOS.a(fyw.tvb,4604L,4604,1);
  check(bar.a(shortcut,(short)4),"native initial insertion");
  Actor actor=(Actor)allocate(Actor.class);actor.controlled=true;
  Manager manager=(Manager)allocate(Manager.class);manager.bar=bar;actor.manager=manager;
  Fight fight=(Fight)allocate(Fight.class);fight.registered=true;fight.actor=actor;actor.fight=fight;
  Spell spell=new Spell();spell.uid=4604;spell.reference=4604;spell.value=1;
  check(NativeSpellGrantShortcut.ensure(actor,(byte)2,(short)0,spell)==shortcut,"exact existing owned shortcut must be reused");
  check(actor.calls==0&&bar.a(shortcut)==4,"repeat must preserve user configured position");
  for(int i=0;i<50;i++)check(NativeSpellGrantShortcut.ensure(actor,(byte)2,(short)0,spell)==shortcut,"repeated grant");
  check(actor.calls==0,"repeat invoked native duplicate insertion");
  spell.reference=4603;NativeSpellGrantShortcut.ensure(actor,(byte)2,(short)0,spell);check(actor.calls==1,"reference mismatch delegated");spell.reference=4604;
  spell.value=2;NativeSpellGrantShortcut.ensure(actor,(byte)2,(short)0,spell);check(actor.calls==2,"value mismatch delegated");spell.value=1;
  NativeSpellGrantShortcut.ensure(actor,(byte)3,(short)0,spell);check(actor.calls==3,"different bar delegated");
  fight.registered=false;NativeSpellGrantShortcut.ensure(actor,(byte)2,(short)0,spell);check(actor.calls==4,"unregistered actor delegated");fight.registered=true;
  actor.controlled=false;NativeSpellGrantShortcut.ensure(actor,(byte)2,(short)0,spell);check(actor.calls==5,"unowned actor delegated");actor.controlled=true;
  bar.c(shortcut);NativeSpellGrantShortcut.ensure(actor,(byte)2,(short)0,spell);check(actor.calls==6,"missing shortcut delegated");
  System.out.println("PASS original bOX inventory; 50 duplicate temporary grants reused exact owned UID and preserved slot4");
  System.out.println("PASS originalcall fallback for different reference/value/bar, unregistered/unowned and missing shortcut");
 }
}

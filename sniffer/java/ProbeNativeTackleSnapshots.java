import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

/** Offline original cuU/eHd/ffh/fei consumption of server-authored snapshots. */
public final class ProbeNativeTackleSnapshots {
 static class Actor extends eGj {
  ffh stats; Sl locator; Battle fight; short level;
  public PA b(PC p){return stats.e(p);} public void a(QM q){} public Qf bax(){return null;}
  public boolean dnz(){return true;} public eGj dpu(){return this;} public byte bcK(){return 0;}
  public byte bcL(){return 0;} public fcb dpt(){return fight;} public boolean a(PE p){return false;}
  public boolean baG(){return false;} public boolean baK(){return false;} public boolean fqx(){return false;}
  public Sl baB(){return locator;} public short cmZ(){return level;}
  public int fqu(){return stats.c(ffw.fK((byte)8));} public int fqv(){return stats.c(ffw.fK((byte)7));}
  public boolean a(PC p){return stats.g(p);}
  public long jy(long v){return 0;} public eGA dnv(){return null;} public Collection<? extends eGj> dnC(){return List.of();}
  public eGj jt(long v){return null;} public foA dnK(){return null;} public fnw dps(){return null;}
  public long dpS(){return 0;} public eHd dpT(){return null;} public void dpQ(){} public boolean dpR(){return false;}
  protected frj dnJ(){return null;} public void Dg(int v){} public long jx(long v){return 0;}
  public eGj b(long v,aBn p,short l,eHD d,SQ s,boolean b,eHN<ffe> h){return null;}
  protected eGH dpU(){return null;} protected byte dpV(){return 0;} public void dnO(){}
  public float dpW(){return 0;} public eRL dpX(){return null;} public void aQc(){}
  public int doX(){return 0;} public int doY(){return 0;} public void c(int v,Object o){} public eGj dpr(){return null;}
 }
 static class Battle extends fcb<Actor> {
  List<Actor> actors;
  Battle(){super(1,null,null);} public fbZ dLv(){return null;} public byte kp(long id){return 0;} public Actor ku(long id){return null;} public Collection<Actor> bJ(byte team){return actors;} public Iterator<PV> bak(){return Collections.emptyIterator();} public List<PV> a(aBn point){return List.of();} public List<PV> b(int x,int y,int z){return List.of();} public long baj(){return 0;} protected void a(fdo d){}
  public fcs dLO(){return null;} public void a(Actor a,List<int[]> p,fcC c){} public void aE(Actor a){} public void dMe(){}
  public void f(Qq q){} public void a(Qq q,amP p){} public void b(Qq q,amP p){} public void g(Qq q){} public void h(Qq q){} public void c(Qq q,amP p){} public void i(Qq q){}
  public Collection<Actor> aI(eGj mover){return new ArrayList<>(actors.stream().filter(a->a!=mover).toList());}
 }
 static sun.misc.Unsafe unsafe()throws Exception{Field f=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);return(sun.misc.Unsafe)f.get(null);}
 static Actor read(Path path,int x,int y,int direction,int level)throws Exception{return read(path,x,y,direction,level,null);}
 static Actor read(Path path,int x,int y,int direction,int level,Actor previous)throws Exception{
  cuU packet=new cuU();packet.dp(Files.readAllBytes(path));byte[] blob=packet.aLJ();
  eHd descriptor=blob[0]==3?new eHk():new eHj();descriptor.ew(blob);
  Method select=eHd.class.getDeclaredMethod("a",eHe.class);select.setAccessible(true);
  ffh stats=previous==null?null:previous.stats;int sections=0;
  for(eHe field:eHf.values()[blob[0]&255].fuK()){
   gp part=(gp)select.invoke(descriptor,field);tA data=null;
   if(part instanceof pl pc)data=pc.SS;
   if(data!=null){ffh parsed=stats==null?new ffh():stats;if(!parsed.b(data))throw new AssertionError("native ffh load");stats=parsed;sections++;}
  }
  if(stats==null)throw new AssertionError("no native PC section format"+blob[0]);
  Actor actor=(Actor)unsafe().allocateInstance(Actor.class);actor.stats=stats;actor.level=(short)level;
  Field p=eGj.class.getDeclaredField("pGF");p.setAccessible(true);p.set(actor,new aBn(x,y,(short)0));
  actor.locator=new Sl();actor.locator.a(x,y,(short)0,aAS.wL(direction));
  System.out.println("SNAPSHOT "+path.getFileName()+" format="+(blob[0]&255)+" sections="+sections+" AP="+stats.c(ffw.fK((byte)2))+" MP="+stats.c(ffw.fK((byte)3))+" LOCK="+stats.c(ffw.fK((byte)7))+" DODGE="+stats.c(ffw.fK((byte)8)));
  return actor;
 }
 static void expect(Actor actor,int ap,int mp,int lock,int dodge){
  int[] keys={2,3,7,8},expected={ap,mp,lock,dodge};
  for(int i=0;i<keys.length;i++)if(actor.stats.c(ffw.fK((byte)keys[i]))!=expected[i])throw new AssertionError("PC"+keys[i]+" mismatch");
 }
 public static void main(String[]args)throws Exception{
  Path dir=Path.of(args[0]);Actor player=read(dir.resolve("player-before.bin"),1,0,5,29),npc=read(dir.resolve("npc-before.bin"),0,0,1,8);
  expect(player,6,5,74,-20);expect(npc,6,3,6,16);
  Battle fight=(Battle)unsafe().allocateInstance(Battle.class);fight.actors=List.of(player,npc);player.fight=npc.fight=fight;
  for(Actor mover:List.of(player,npc)){
   int[] end=mover==player?new int[]{1,1,0}:new int[]{0,1,0};
   List<fej> preview=fei.a(new amK(new int[][]{end}),mover);int ap=0,mp=0;
   for(fej loss:preview){ap+=loss.fYy();mp+=loss.fYz();}
   System.out.println("NATIVE_FEI "+(mover==player?"player":"npc")+" AP="+ap+" MP="+mp);
   String[] expected=Files.readString(dir.resolve(mover==player?"player-cost.txt":"npc-cost.txt")).trim().split(",");
   if(ap!=Integer.parseInt(expected[0])||mp!=Integer.parseInt(expected[1]))throw new AssertionError("server/native tackle mismatch");
  }
  Actor playerAfter=read(dir.resolve("player-after.bin"),1,1,3,29,player),npcAfter=read(dir.resolve("npc-after.bin"),0,1,3,8,npc);
  expect(playerAfter,4,1,74,-20);expect(npcAfter,4,0,6,16);
  if(playerAfter.stats!=player.stats||npcAfter.stats!=npc.stats)throw new AssertionError("snapshot did not update existing native manager");
  for(String kind:List.of("player","npc")){cuU properties=new cuU();properties.dp(Files.readAllBytes(dir.resolve(kind+"-after-properties.bin")));eHd descriptor=kind.equals("player")?new eHk():new eHj();descriptor.ew(properties.aLJ());if(properties.aLJ()[0]!=26)throw new AssertionError("missing native properties restoration");}
  if(playerAfter.stats.c(ffw.fK((byte)2))!=4||playerAfter.stats.c(ffw.fK((byte)3))!=1)throw new AssertionError("player postpayment");
  if(npcAfter.stats.c(ffw.fK((byte)2))!=4||npcAfter.stats.c(ffw.fK((byte)3))!=0)throw new AssertionError("NPC postpayment");
  System.out.println("PASS 21 checks: 16 PC getters, 2 native fei/server costs, 1 existing-manager update, 2 format26 restores; no GUI/session claim");
 }
}

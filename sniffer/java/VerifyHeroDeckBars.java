import java.nio.*;import java.nio.file.*;import java.lang.reflect.*;import java.util.*;
/** Exercises the installed client deck-to-spell-bar presentation without casting. */
public final class VerifyHeroDeckBars {
 static void set(Object o,Class<?> c,String n,Object v)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 public static void main(String[]a)throws Exception{try{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  cue p=new cue();p.dp(Files.readAllBytes(Path.of(a[0])));byte[]e=p.eGo();
  VerifyHeroWorldResources.OfflineActor actor=new VerifyHeroWorldResources.OfflineActor();
  actor.dtj().a(actor.dtj().fsS(),e);actor.dtj().a(actor.dtj().fsR(),e);
  actor.dtj().a(actor.dtj().fvG(),e);actor.dtj().a(actor.dtj().fwi(),e);
  set(actor,biB.class,"iax",eQV.ez(p.eFc()));
  aTJ account=new aTJ();account.oh(actor.Xi());set(aTx.cWt(),aTx.class,"hsh",account);set(aTx.cWt(),aTx.class,"hsi",actor);
  csZ stats=new csZ();stats.dp(Files.readAllBytes(Path.of(a[1])));actor.dtj().a(actor.dtj().fve(),stats.eFf());
  fzf deck=actor.drs();if(deck==null)throw new AssertionError("active build has no native deck");
  System.out.println("actor="+actor.Sn()+" realLevel="+actor.drm()+" deckAllowed="+deck.ak(actor)+" active="+deck.eNR());
  bQm.a(deck,actor.dok(),actor.dpp());
  List<Integer>icons=new ArrayList<>();for(byte bar=0;bar<2;bar++){var it=actor.dpp().ck(bar).ejM();while(it.hasNext()){it.advance();icons.add(it.value().awe());}}
  System.out.println("native bar icons="+icons);
  if(icons.isEmpty())throw new AssertionError("native spell bars empty");
  System.out.println("PASS native active build/deck→bQm spell-bar presentation");
 }catch(Throwable t){t.printStackTrace();System.exit(1);}System.exit(0);}
}

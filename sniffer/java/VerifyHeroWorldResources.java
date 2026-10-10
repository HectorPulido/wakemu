import java.nio.*;import java.nio.file.*;import java.lang.reflect.*;
/** Exercises native owned actor HP hydration and the existing world progression refresh. */
public final class VerifyHeroWorldResources {
 static final class OfflineActor extends biB {OfflineActor(){super(false);} @Override public void a(PA change) {} @Override public Qf bax(){return null;} @Override public bPo drI(){return null;}}
 public static void main(String[]a)throws Exception{try{
  cue admission=new cue();admission.dp(Files.readAllBytes(Path.of(a[0])));byte[]owned=admission.eGo();
  biB actor=new OfflineActor();actor.dtj().a(actor.dtj().fsS(),owned);actor.dtj().a(actor.dtj().fsR(),owned);
  fkK.suH.d(actor.Xi(),actor);fkK.suH.ay(actor.Xi(),actor.Sn());
  actor.dtj().a(actor.dtj().fvd(),owned);
  System.out.println("initial HP="+actor.e(ffw.sgC).aYS()+" max="+actor.e(ffw.sgC).aYU());
  byte[]body=Files.readAllBytes(Path.of(a[1]));ByteBuffer.wrap(body).putLong(actor.Sn());csZ refresh=new csZ();refresh.dp(body);
  actor.dtj().a(actor.dtj().fsX(),refresh.eFf());
  actor.dtj().a(actor.dtj().fve(),refresh.eFf());
  System.out.println("refreshed HP="+actor.e(ffw.sgC).aYS()+" max="+actor.e(ffw.sgC).aYU()+" realLevel="+actor.drm());
  if(actor.e(ffw.sgC).aYU()==Integer.MAX_VALUE)throw new AssertionError("missing maxHP");
  System.out.println("PASS native HP/public-characteristics/XP consumers initialize finite owned resources");
 }catch(Throwable t){t.printStackTrace();System.exit(1);}System.exit(0);}
}

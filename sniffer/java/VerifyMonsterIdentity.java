import java.nio.file.*;
/** Decode owned world NPCs with the installed codec; no renderer or network. */
public class VerifyMonsterIdentity{
 public static void main(String[]args)throws Exception{
  long actor=Long.parseLong(args[1]),group=Long.parseLong(args[2]);
  ctE message=new ctE();if(!message.dp(Files.readAllBytes(Path.of(args[0])))||message.eFQ().size()!=1)throw new AssertionError("Spawn parse failed");
  ctF entry=message.eFQ().get(0);eHj npc=new eHj();npc.ew(entry.aLJ());
  if(entry.Sn()!=actor||npc.fsS().Vc!=actor||npc.fuY().ZW!=group)throw new AssertionError("Identity changed");
  if(npc.fsW().Ue!=-1)throw new AssertionError("Unexpected fight");
  System.out.println("Native actor/group i64 preserved: "+actor+" / "+group);
 }
}

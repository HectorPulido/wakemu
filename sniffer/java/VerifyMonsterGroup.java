import java.nio.file.*;
/** Read-only checks against installed Java codecs; fixtures contain own IDs. */
public class VerifyMonsterGroup {
 static void check(boolean value){if(!value)throw new AssertionError();}
 static void world(byte[] blob,long actor){
  eHj data=new eHj();data.ew(blob);check(data.fsS().Vc==actor);
  sU roster=data.fuY();check(roster.ZW==501&&roster.ZX.size()==2);
  for(sW member:roster.ZX)check(member.SC==5525&&member.Yf==1);
 }
 public static void main(String[]args)throws Exception {
  ctA remove=new ctA();check(remove.dp(Files.readAllBytes(Path.of(".runtime/local/group-remove.bin"))));
  check(!remove.eFH()&&!remove.eFI()&&remove.eFG().size()==2);
  check(remove.eFG().get(0).getFirst()==1&&remove.eFG().get(0).aIy()==-200);
  check(remove.eFG().get(1).getFirst()==1&&remove.eFG().get(1).aIy()==-201);
  ctE spawn=new ctE();spawn.dp(Files.readAllBytes(Path.of(".runtime/local/group-spawn.bin")));
  check(spawn.eFQ().size()==2);
  for(ctF member:spawn.eFQ()){check(member.aGJ()==1);world(member.aLJ(),member.Sn());}
  cvb bootstrap=new cvb();bootstrap.dp(Files.readAllBytes(Path.of(".runtime/local/group-bootstrap.bin")));
  check(bootstrap.bhe()==77&&bootstrap.eHa()==3);
  check(bootstrap.Mj(0)==1&&bootstrap.Mj(1)==-200&&bootstrap.Mj(2)==-201);
  for(int i=1;i<3;i++){eHj npc=new eHj();npc.ew(bootstrap.Mn(i));check(npc.fsS().Vc==bootstrap.Mj(i));}
  check(bootstrap.eHs()==1&&bootstrap.eHt()==-200);
  System.out.println("Native ctE/eHj2-member roster and cvb3-participant identity/leader consistency verified");
 }
}

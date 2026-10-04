import java.nio.file.*;
public final class VerifyMonsterCollect {
 public static void main(String[] args)throws Exception{
  byte[] body=Files.readAllBytes(Path.of(args[0]));cta message=new cta();
  if(body.length!=31||!message.dp(body)||message.eLS()!=6||message.eKl()!=7||message.eFh()!=3000L||message.eFi()!=-4498523304664558568L||message.eFg()!=3723)throw new AssertionError("Native monster harvest mismatch");
  System.out.println("cta13597: own actor7, full i64 target, duration3000ms, action3723 verified");
 }
}

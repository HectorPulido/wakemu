import java.nio.file.*;import java.util.*;
/** Validate each owned ZAAP context with the installed current native decoders. */
public class VerifyNativeZaapContexts {
 public static void main(String[]args)throws Exception {
  int count=0;
  for(Path p:Files.list(Path.of(args[0])).sorted().toList()) {
   String[] expected=p.getFileName().toString().replace(".bin","").split("_");
   long map=Long.parseLong(expected[0]);int x=Integer.parseInt(expected[1]),y=Integer.parseInt(expected[2]);short z=Short.parseShort(expected[3]);
   csW message=new csW();if(!message.dp(Files.readAllBytes(p)))throw new AssertionError("csW");
   eHk entity=new eHk();entity.a(entity.fsV(),message.eEX());rE position=entity.fsV();
   if(position.Vp!=map||position.XC!=x||position.XD!=y||position.XE!=z)throw new AssertionError("Native destination differs: "+p);
   eUZ context=eVa.eD(message.eFa());
   if(!Arrays.equals(eVa.b(context),eVa.b(new eUZ())))throw new AssertionError("Foreign context");
   if(!message.eEY().isEmpty()||!message.eEZ().isEmpty())throw new AssertionError("Inherited fights");
   count++;
  }
  System.out.println("Native csW/rE/eVa valid owned ZAAP contexts="+count);
 }
}

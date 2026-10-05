import java.nio.file.*;
public class ProbeNativeLifeStealCodec {public static void main(String[]args)throws Exception{
 cvX packet=new cvX();if(!packet.dp(Files.readAllBytes(Path.of(args[0])))||packet.eII()!=24)throw new AssertionError("cvX24");
 eXv runner=new eXv();runner.lV(24);iN data=runner.ds(packet.eIJ());
 if(data==null||runner.LV()!=99||runner.getValue()!=12||data.Qs()!=3188||data.Qw()!=7||data.Qy()!=-7)throw new AssertionError("native healing identity/value");
 System.out.println("PASS actual cvX24/eXv healing UID99/ref3188/caster7/target-7/value12");
}}

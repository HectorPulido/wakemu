import java.nio.file.*;
public class VerifyPlantingPackets {public static void main(String[]args)throws Exception{
 cAz create=new cAz();create.dp(Files.readAllBytes(Path.of(".runtime/local/planting-create.bin")));zk r=create.eNq();if(r.acs()!=823||r.getX()!=10||r.getY()!=-11||r.NN()!=0||r.axr()!=1||r.axv()!=123)throw new AssertionError();
 cAZ result=new cAZ();result.dp(Files.readAllBytes(Path.of(".runtime/local/planting-result.bin")));if(!result.aHi())throw new AssertionError();
 cyK start=new cyK();start.dp(Files.readAllBytes(Path.of(".runtime/local/planting-start.bin")));if(start.cmG()!=74)throw new AssertionError();System.out.println("native13135/12954/12815 parsers OK");}}

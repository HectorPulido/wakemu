import java.nio.*;
import java.util.*;
/** Offline native capacity decoding and selection UI model verification. */
public class VerifyCharacterCapacity {
 public static void main(String[] args)throws Exception{
  if(!"5".equals(eEL.oZT.getDefaultValue().toString()))throw new AssertionError("native free-slot default");
  eEI.oZx.a(eEL.oZT,"5");
  for(int maximum:new int[]{1,5,18,24,127}){
   cEl update=new cEl();update.dp(new byte[]{(byte)(maximum-5)});
   bkg.imU.b(update.ePr(),new ArrayList<big>());
   if(!Integer.valueOf(maximum).equals(bkg.imU.eH("maxCharacterCount")))throw new AssertionError("UI cap "+maximum);
  }
  ByteBuffer bytes=ByteBuffer.allocate(1+127*4+1);bytes.put((byte)127);for(int n=0;n<127;n++)bytes.putInt(0);bytes.put((byte)0);
  cEk roster=new cEk();roster.dp(bytes.array());if(roster.ePp().size()!=127)throw new AssertionError("127 roster");
  cEk overflow=new cEk();overflow.dp(new byte[]{(byte)128,0});if(!overflow.ePp().isEmpty())throw new AssertionError("signed roster overflow");
  System.out.println("PASS native UI capacity1/5/18/24/127 and signed roster127/128 boundary; free slots="+eEL.oZT.getDefaultValue());
 }
}

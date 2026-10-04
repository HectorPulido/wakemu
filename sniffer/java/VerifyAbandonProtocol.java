import java.nio.*;
public class VerifyAbandonProtocol{public static void main(String[]args)throws Exception{
 byte[]request=new cpf().aWH();ByteBuffer r=ByteBuffer.wrap(request);if(r.getInt()!=7||r.get()!=3||(r.getShort()&65535)!=13952||r.hasRemaining())throw new AssertionError("cpf request mismatch");
 byte[]body=ByteBuffer.allocate(13).putInt(7).putInt(1).putInt(-1).put((byte)1).array();cvF finish=new cvF();if(!finish.dp(body)||!finish.eIn()||finish.bhe()!=7)throw new AssertionError("cvF abort mismatch");
 coQ continuation=new coQ(7,false);byte[]wire=continuation.aWH();ByteBuffer c=ByteBuffer.wrap(wire);if(c.getInt()!=12||c.get()!=3||(c.getShort()&65535)!=12925||c.getInt()!=7||c.get()!=0||c.hasRemaining())throw new AssertionError("coQ continuation mismatch");
 System.out.println("Native cpf13952 empty -> cvF12238 huN=true -> coQ12925 matching fight verified");
}}

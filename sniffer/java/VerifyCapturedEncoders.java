import java.nio.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
public class VerifyCapturedEncoders {
 static String text(ByteBuffer b){byte[] bytes=new byte[b.getInt()];b.get(bytes);return new String(bytes,java.nio.charset.StandardCharsets.UTF_8);}
 public static void main(String[] args)throws Exception {
  int checked=0,skipped=0;
  for(String line:Files.readAllLines(Path.of(args[0]))) {
   var r=JsonParser.parseString(line).getAsJsonObject();if(!r.get("direction").getAsString().equals("out"))continue;
   int op=r.get("opcode").getAsInt(),route=r.get("route").getAsInt();byte[] body=Base64.getDecoder().decode(r.get("body_base64").getAsString());ByteBuffer b=ByteBuffer.wrap(body);azW msg;
   switch(op) {
    case 33:{cmP m=new cmP();m.el(body);msg=m;break;}
    case 574:msg=new cmO((byte)route);break;
    case 584:{cmL m=new cmL();byte[] encrypted=new byte[b.getInt()];b.get(encrypted);m.ek(encrypted);msg=m;break;}
    case 402:msg=new cmN();break;
    case 575:{cmS m=new cmS();m.zY(b.getInt());m.J(b.get()==1?b.getLong():null);msg=m;break;}
    case 426:{cmG m=new cmG();m.lQ(text(b));m.pI(text(b));msg=m;break;}
    case 22954:msg=new cDT(text(b));break;
    case 23664:{cDR m=new cDR();m.db(b.getLong());m.jG(text(b));msg=m;break;}
    case 12225:msg=new csD(b.getLong());break;
    case 12851:{cpP m=new cpP();m.db(b.getLong());msg=m;break;}
    case 13003:{cpo m=new cpo();m.pJ(new String(body,java.nio.charset.StandardCharsets.UTF_8));msg=m;break;}
    case 12010:{cqp m=new cqp();m.m(ML.A(b.get()));m.b(UH.pQ(b.get()));msg=m;break;}
    case 1026:msg=new OA();break;
    case 14689:msg=new cDt();break;
    case 13331:{cnl m=new cnl();m.b(ada.rY(b.getInt()));m.c(aAT.eY(b));msg=m;break;}
    default:skipped++;continue;
   }
   byte[] encoded=msg.aWH();ByteBuffer expected=ByteBuffer.allocate(body.length+7);expected.putInt(body.length+7).put((byte)route).putShort((short)op).put(body);
   if(!Arrays.equals(encoded,expected.array()))throw new AssertionError("Encoder mismatch opcode="+op+" seq="+r.get("capture_seq"));checked++;
  }
  System.out.println("Exact JAR encoder matches: "+checked+"; unresolved generic requests skipped: "+skipped);
 }
}

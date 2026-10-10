import java.nio.*;
import java.util.*;
/** Headless checks of real account knowledge and native occupation decoders. */
public class VerifyEmoteProtocol {
 public static void main(String[] args)throws Exception{
  fbs known=new fbs(); if(!known.Tp(42)||!known.Tr(42))throw new AssertionError("native add");
  byte[] wire=known.foH(); fbs decoded=new fbs();decoded.a(1L,ByteBuffer.wrap(wire));decoded.a(1L,ByteBuffer.wrap(wire));
  if(!decoded.Tr(42)||decoded.fTR().size()!=1)throw new AssertionError("idempotent knowledge");
  hI proto=hI.aS(Arrays.copyOfRange(wire,4,wire.length));
  if(proto.JU().get(0).d()!=42)throw new AssertionError("protobuf item");
  for(var field:hE.JH().getFields())System.out.println("hE "+field.getNumber()+" "+field.getName()+" "+field.getType());
  for(var field:hI.JT().getFields())System.out.println("hI "+field.getNumber()+" "+field.getName()+" "+field.getType());
  byte[] payload=ByteBuffer.allocate(5).putInt(42).put((byte)0).array();
  cyN broadcast=new cyN();broadcast.dp(ByteBuffer.allocate(20).put((byte)1).putShort((short)20).putLong(99L).putInt(5).put(payload).array());
  if(broadcast.d()!=12088||broadcast.eLS()!=20||broadcast.eKl()!=99L||broadcast.eKk()!=1)throw new AssertionError("occupation");
  var uf=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");uf.setAccessible(true);var unsafe=(sun.misc.Unsafe)uf.get(null);
  blU occupation=(blU)unsafe.allocateInstance(blU.class);var values=blU.class.getDeclaredField("iwf");values.setAccessible(true);values.set(occupation,new HashMap<String,Object>());occupation.dX(broadcast.aLJ());
  var id=blU.class.getDeclaredField("ezG");id.setAccessible(true);if(id.getInt(occupation)!=42)throw new AssertionError("emote payload");
  byte[] targeted=ByteBuffer.allocate(25).putInt(20069).put((byte)1).putInt(8).put("targetId".getBytes(java.nio.charset.StandardCharsets.UTF_8)).putLong(123L).array();
  occupation.dX(targeted);if(!Long.valueOf(123).equals(((Map<?,?>)values.get(occupation)).get("targetId")))throw new AssertionError("target parameter");
  cnn request=new cnn();request.LS(42);request.fe(-1);if(request.d()!=13498)throw new AssertionError("request");
  cuF ack=new cuF();ack.dp(ByteBuffer.allocate(5).putInt(42).put((byte)1).array());if(ack.d()!=12266||ack.eGO()!=42||!ack.aHi())throw new AssertionError("ack");
  System.out.println("PASS native account EMOTES restore and native blU/cyN occupation/ack decoders");
 }
}

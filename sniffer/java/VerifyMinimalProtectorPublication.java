import java.nio.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
/** Native minimal protector identity publication, with no captured economic state. */
public class VerifyMinimalProtectorPublication {
 public static void main(String[] args)throws Exception{
  org.apache.log4j.BasicConfigurator.configure();
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  cdH.bla();
  cdH.exY().dW("jar:file:"+Path.of("client/contents/maps/data.jar").toAbsolutePath()+"!/worlds.lib");
  if(fxf.toy.Zp(93601)==null||fxf.toy.Zp(93601).arM()!=1385L) throw new AssertionError("Native territory93601 notmap1385");
  long actor=Long.parseLong(args[0]);
  wW state=new wW();state.aiQ=424;state.aiR=new xh();state.aiR.ajC=0;state.aiR.ajD=0;state.aiR.ajE=93601;state.aiS=new wX();state.aiS.aje=22193;state.aiS.ajf=actor;
  byte[] record=bMa.kvt.a(state);
  ByteBuffer decodedBytes=ByteBuffer.wrap(record);wW decoded=new wW();
  if(!decoded.aG(decodedBytes)||decodedBytes.hasRemaining()||decoded.aiQ!=424||decoded.aiS.ajf!=actor)
   throw new AssertionError("Protector identity record mismatch");
  bLO protector=(bLO)bMd.kvy.gt(ByteBuffer.wrap(record));
  if(protector.d()!=424||protector.cXS()!=actor)throw new AssertionError("Native manager actor link mismatch");
  bLU.kvl.c(protector);
  bLO registered=(bLO)bLU.kvl.Zo(424);
  if(registered==null||registered.cXS()!=actor)throw new AssertionError("Protector registry mismatch");
  byte[] list=ByteBuffer.allocate(4+record.length).putShort((short)1).putShort((short)record.length).put(record).array();
  byte[] entity=new byte[0],other=new byte[]{0,0},context=new byte[0];
  ByteBuffer snapshot=ByteBuffer.allocate(8+entity.length+list.length+other.length+context.length);
  for(byte[] block:new byte[][]{entity,list,other,context})snapshot.putShort((short)block.length).put(block);
  csW world=new csW();if(!world.dp(snapshot.array())||world.eEY().size()!=1||!Arrays.equals(world.eEY().getFirst(),record))
   throw new AssertionError("13974 protector list mismatch");
  Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("protector_id",424,"actor_id",actor,"record_hex",HexFormat.of().formatHex(record),"list_hex",HexFormat.of().formatHex(list),"native_record",new Gson().toJsonTree(decoded))));
  System.out.println("native_wW_roundtrip=PASS bMd_actor_link=PASS bLU_registry=PASS csW_list=PASS record_bytes="+record.length);
 }
}

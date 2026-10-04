import java.nio.file.*;import com.google.gson.*;
/** Exact installed object states parsed by actual current cwJ and bEu codecs. */
public class VerifyNativeTransportObjects{public static void main(String[]a)throws Exception{
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
 JsonArray rows=JsonParser.parseString(Files.readString(Path.of(a[0]))).getAsJsonArray();int count=0;
 for(JsonElement v:rows){JsonObject row=v.getAsJsonObject();byte[] payload=java.util.HexFormat.of().parseHex(row.get("payload_hex").getAsString());bEG object=(row.get("type").getAsString().equals("Drago")?bEE.valueOf("Drago"):bEE.valueOf("Zaap")).bej().bau();object.as(payload);
 if(object.getWorldX()!=row.get("x").getAsFloat()||object.getWorldY()!=row.get("y").getAsFloat()||object.getAltitude()!=row.get("z").getAsFloat())throw new AssertionError("Native transport position mismatch");
 java.nio.ByteBuffer b=java.nio.ByteBuffer.allocate(12+payload.length);b.putShort((short)1).putLong(row.get("id").getAsLong()).putShort((short)payload.length).put(payload);cwJ state=new cwJ();if(!state.dp(b.array())||state.cie().size()!=1)throw new AssertionError("cwJ");count++;
 }
 System.out.println("Native bEu/cwJ transport objects="+count);
}}

import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import com.google.gson.Gson;
import io.netty.channel.embedded.EmbeddedChannel;
import io.netty.buffer.ByteBuf;

/** Exercises original intergame auth framing and inbound protobuf decoding offline. */
public final class VerifyNativeIntergameCodec {
    private static void check(boolean condition,String message) {if(!condition)throw new AssertionError(message);}
    public static void main(String[] args)throws Exception {
        aZe auth=new aZe();auth.lQ("offline-single-use-token");auth.Ap(2);auth.Aq(1);auth.Ar(3);auth.lR("WakfuUser");auth.lS("");
        EmbeddedChannel encoder=new EmbeddedChannel(new aYP(),new aYN());
        check(encoder.writeOutbound(auth),"Native auth encoder emitted no frame");
        ByteBuf frame=encoder.readOutbound();int total=frame.readInt();
        check(total==frame.readableBytes()+4 && frame.readByte()==0,"Native auth frame header");
        String json=frame.toString(StandardCharsets.UTF_8);
        check(json.contains("\"token\":\"offline-single-use-token\"") && json.contains("\"clientType\":2"),"Native auth JSON names");
        aZf accepted=new Gson().fromJson("{\"success\":true,\"errCode\":0}",aZf.class);
        check(accepted.aHi()&&accepted.dbq()==0,"Original auth response decoder");
        frame.release();encoder.finishAndReleaseAll();
        System.out.println("PASS original aYN/aYP auth JSON frame; original aZf successful auth response");
        if(args.length==0) {System.out.println("LIMIT no server incoming fixture supplied");return;}
        byte[] raw=Files.readAllBytes(Path.of(args[0]));
        am envelope=am.m(raw);List<Object> decoded=new ArrayList<>();new aYL().a(null,envelope,decoded);
        if(decoded.size()==1 && decoded.get(0) instanceof bq friends) {
            aTJ account=new aTJ();account.oh(5);
            var current=aTx.class.getDeclaredField("hsh");current.setAccessible(true);current.set(aTx.cWt(),account);
            new aYV().a(null,friends);
            check(friends.ak()==1,"Expected one native friend");
            check(aOD.eAd.V("Peer","6").orElseThrow().equals("DM_5_6"),"Native friend resolver channel");
            System.out.println("PASS negative FriendList ID through original am/aYL/bq/aYV and native directory resolves Peer#6 to DM_5_6");return;
        }
        check(decoded.size()==1&&decoded.get(0) instanceof l,"Native incoming must decode ChannelMessageCreatedEvt");
        i message=((l)decoded.get(0)).R();
        check(message.n().equals(args[1]),"Incoming channel ID");
        check(message.q().equals(args[2]),"Incoming content");
        check(message.t().fD()==Long.parseLong(args[3]),"Incoming author account ID");
        System.out.println("PASS original am/aYL/l/i incoming event channel="+message.n()+" author="+message.t().fD());
        System.out.println("LIMIT UI aYU rendering is not executed by this codec oracle");
    }
}

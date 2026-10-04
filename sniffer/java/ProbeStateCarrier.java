import java.nio.file.*;
import java.lang.reflect.Proxy;
/** Native owned state310 serialization, including its independent carrier UID. */
public class ProbeStateCarrier {
    static PV actor(long id) {
        return (PV) Proxy.newProxyInstance(PV.class.getClassLoader(), new Class<?>[]{PV.class},
            (object, method, args) -> switch(method.getName()) {
                case "Sn" -> id;
                case "bcz", "bcA" -> 0;
                case "bcB" -> (short)0;
                case "bcy" -> aAS.dyA;
                case "toString" -> "OwnedActor" + id;
                default -> throw new UnsupportedOperationException(method.getName());
            });
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        fyZ.guX().a(new bbV());
        int value = fyW.ae((short)3442, (short)1);
        eZk state = eZk.a(null, actor(22), null, value);
        if(state == null) throw new AssertionError("Native state3442 missing");
        state.f(actor(-33)); state.dg(2345); state.dj(1234);
        iN proto = state.bca();
        if(state.d()!=310 || proto.LV()!=2345 || proto.QA().LV()!=2345
                || proto.Qq()!=1234 || proto.getValue()!=value || proto.QA().getValue()!=value
                || proto.Qw()!=22 || proto.Qy()!=-33 || state.fQW().guI()!=3442) {
            throw new AssertionError("Native state carrier identities/packed value");
        }
        Files.write(Path.of(args[0]), proto.toByteArray());
        System.out.println("proto: uid=" + proto.LV() + ", base=" + proto.Qq()
            + ", generic=" + proto.Qs() + ", value=" + proto.getValue()
            + ", caster=" + proto.Qw() + ", target=" + proto.Qy());
        ij additional = proto.QA();
        System.out.println("additional: uid13=" + additional.LV() + ", packed10=" + additional.getValue()
            + ", duration21=" + additional.Mk() + ", realtime22=" + additional.Mm()
            + ", related50=" + additional.MJ() + ", flag17=" + additional.Mc()
            + ", flag18=" + additional.Me() + ", critical19=" + additional.Mg());
        System.out.println(java.util.HexFormat.of().formatHex(proto.toByteArray()));
        if(args.length > 1) {
            cvY application = new cvY();
            if(!application.dp(Files.readAllBytes(Path.of(args[1]))) || application.d()!=13497
                    || !application.eIc().toString().equals("EFFECT_APPLICATION")
                    || application.eII()!=310) throw new AssertionError("Native carrier application codec");
            eZk received = new eZk(); received.lV(310);
            iN receivedProto = received.ds(application.eIJ());
            if(receivedProto==null || received.LV()!=2345 || received.getValue()!=value
                    || received.fQW()==null || received.fQW().guI()!=3442
                    || received.fQW().cmZ()!=1 || receivedProto.Qw()!=22
                    || receivedProto.Qy()!=-33 || receivedProto.Qq()!=1234) {
                throw new AssertionError("Native owned carrier application/state lookup");
            }
            System.out.println("13497 cvY application deserialized into real eZk state3442 with matching UID2345");
        }
        System.out.println("Owned state3442 carrier310 UID2345 and parent UID1234 verified");
    }
}

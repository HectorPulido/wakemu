import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;

/** Decode locally generated cvZ removal with the actual client codec. */
public class VerifyEffectRemoval {
    public static void main(String[] args) throws Exception {
        byte[] body = Files.readAllBytes(Path.of(args[0]));
        int fight = Integer.parseInt(args[1]), action = Integer.parseInt(args[2]);
        int effectClass = Integer.parseInt(args[3]);
        long target = Long.parseLong(args[4]), uid = Long.parseLong(args[5]);
        cvZ command = new cvZ();
        if (!command.dp(body) || command.d() != 13560
                || !command.eIc().toString().equals("EFFECT_UNAPPLICATION")) {
            throw new AssertionError("Native effect removal codec/opcode");
        }
        if (command.bhe() != fight || command.cbc() != action
                || command.eId() != -1 || command.eII() != effectClass
                || command.Qy() != target || command.eIL() != uid) {
            throw new AssertionError("Native removal action identities");
        }
        iN proto = iN.bf(command.eIJ());
        if (proto.LV() != uid || proto.Qy() != target || !proto.isInitialized()
                || !Arrays.equals(command.eIJ(), Arrays.copyOfRange(body, 18, body.length - 16))) {
            throw new AssertionError("Native owned running-effect protobuf");
        }
        Qf manager = new Qf() {
            public Qi bci() { return null; }
            public void r(Qe effect) {} // Isolate registry deletion from visual side effects.
        };
        eZR effect = effectClass == 310 ? new eZk() : new eXt();
        eZR other = new eXt();
        if (effectClass == 310) {
            if (eVi.rpJ.d() != 310 || !(eVi.fLJ().pS(310) instanceof eZk)
                    || !proto.Qz() || proto.QA().LV() != uid) {
                throw new AssertionError("Native state310 carrier or AdditionalDatas UID");
            }
        }
        effect.dg(uid); other.dg(uid + 1);
        manager.p(effect); manager.p(other);
        Qe owned = manager.dk(command.eIL());
        if (owned != effect || owned.ds(command.eIJ()) == null
                || owned.LV() != uid || !manager.q(owned) || manager.dk(uid) != null
                || manager.dk(uid + 1) != other) {
            throw new AssertionError("Native UID lookup/removal affected another running effect");
        }
        System.out.println("13560 cvZ EFFECT_UNAPPLICATION: owned target=" + target
                + " UID=" + uid + ", effect_class=" + effectClass
                + ", native proto initialized/preserved; native manager removed only owned UID");
    }
}

import java.nio.ByteBuffer;
import java.util.HexFormat;

/** Check physical, equipment and identification elemental carriers together. */
public final class VerifyItemElementRegistries {
    public static void main(String[] args) throws Exception {
        if (args.length != 3) throw new IllegalArgumentException("usage: <item-form> <item-proto> <13766-body>");
        vj physical = new vj();
        if (!physical.aG(ByteBuffer.wrap(HexFormat.of().parseHex(args[0]))) || physical.afy == null)
            throw new AssertionError("Physical item lacks native elements");
        kX equipment = kX.bG(HexFormat.of().parseHex(args[1]));
        if (!equipment.aec()) throw new AssertionError("Equipment item lacks native elements");
        vR masks = new vR();
        masks.agG = (byte) equipment.aed().afm();
        masks.agH = (byte) equipment.aed().afo();
        foX equipmentElements = foX.b(masks);
        foX physicalElements = foX.b(physical.afy.afH);
        cxh identification = new cxh();
        if (!identification.dp(HexFormat.of().parseHex(args[2])))
            throw new AssertionError("Identification response rejected");
        if (physicalElements.aKv() || equipmentElements.aKv() || identification.eJZ() == null
                || identification.eJZ().aKv()) throw new AssertionError("Native elemental choice still pending");
        if (masks.agG != physical.afy.afH.agG || masks.agH != physical.afy.afH.agH)
            throw new AssertionError("Physical/equipment choices differ");
        System.out.println("PASS physical/equipment/13766 elements agree; pending=false; damage="
                + masks.agG + " resistance=" + masks.agH);
    }
}

import java.nio.ByteBuffer;
import java.util.HexFormat;

/** Bounded original vJ/vK/up serialization; no native game catalogs. */
public final class ProbeNativeCharacterCopyCodec {
    public static void main(String[] args) {
        for (int n = 0; n < 2; n++) {
            vJ descriptor = new vJ();
            descriptor.agn = (short) (n == 0 ? 1620 : -32768);
            descriptor.VY = n == 0 ? "Copied Héctor" : null;
            descriptor.ago = n == 0 ? 1 : Integer.MIN_VALUE;
            descriptor.agp = n == 0 ? 295 : Long.MIN_VALUE;
            descriptor.Yf = (short) (n == 0 ? 200 : -32768);
            descriptor.Uj = (byte) (n == 0 ? 17 : -128);
            descriptor.ags = n == 0 ? -1 : 9;
            descriptor.agt = n == 0 ? 7 : Long.MAX_VALUE;
            descriptor.agu = n != 0;
            descriptor.agq = new vK();
            up appearance = descriptor.agq.agv;
            appearance.ade = n == 0 ? 100 : Integer.MAX_VALUE;
            appearance.adf = n == 0 ? 12345 : Integer.MIN_VALUE;
            appearance.Su = new byte[] {8, 1, 16, 2};
            appearance.adg = 1;
            if (n == 0) {
                yD action = new yD();
                action.amt.aaq = 123456789012L;
                action.amt.amm = 6266;
                action.amt.Yf = 200;
                appearance.adh.ams.add(action);
                tB stat = new tB();
                stat.Sj = 1;
                stat.abj = 140;
                stat.abk = 330;
                stat.abl = 0;
                stat.abm = 10000;
                appearance.adi.abi.add(stat);
                uq category = new uq();
                category.TU = -3;
                category.abE = 9876;
                appearance.adj.add(category);
            }
            ByteBuffer output = ByteBuffer.allocate(4096);
            if (!descriptor.aF(output)) throw new AssertionError("Native codec rejected");
            byte[] bytes = new byte[output.position()];
            output.flip(); output.get(bytes);
            System.out.println(HexFormat.of().formatHex(bytes));
        }
    }
}

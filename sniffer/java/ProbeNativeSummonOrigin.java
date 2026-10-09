/** Native eGz/eHD origin field; no client, world or monster spell execution. */
public class ProbeNativeSummonOrigin {
    public static void main(String[] args) {
        bjm state = new bjm();
        eHD descriptor = new eHD((short)3798, "", 0, (short)20);
        if (state.dTC() || descriptor.dTC() || new eHD().dTC())
            throw new AssertionError("Fresh native origin must be false");
        state.a(descriptor);
        if (state.dTC()) throw new AssertionError("Fresh attached origin");
        descriptor.lE(true);
        if (!state.dTC()) throw new AssertionError("Actual descriptor setter");
        descriptor.lE(false);
        if (state.dTC()) throw new AssertionError("Actual descriptor clear");
        System.out.println("6 native origin assertions PASS");
    }
}

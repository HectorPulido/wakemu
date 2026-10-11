/** Offline native faV property enum namespaces and inherited hour semantics. */
public final class ProbeNativeAreaFightPropertyNamespace {
    static final class Hour extends faZ {
        public boolean fTq() { return false; }
        public java.util.List<amP> d(amP value) { return n(value); }
        protected Qq bcs() { return new Hour(); }
        public int df(long id) { return 0; }
        public byte bav() { return 0; }
        public byte[] baz() { return new byte[0]; }
        public anS bEs() { return null; }
        public void a(int x, int y, short z, Qe source) {}
    }
    public static void main(String[] args) {
        int count = 0;
        Hour hour = new Hour();
        for (int id = 0; id < 15; id++) hour.f(fbo.Tn(id));
        for (ffe property : ffe.values()) {
            if (property.aZu() != 1 || hour.a(property)) throw new AssertionError(property);
            hour.a(property, (byte) 1);
            if (hour.a(property)) throw new AssertionError("faV accepted foreign namespace");
            count++;
        }
        for (int id = 0; id < 15; id++) {
            if (!hour.a(fbo.Tn(id))) throw new AssertionError("lost actual fbo property");
        }
        System.out.println("PASS inherited faZ/faV: " + count
            + " ffe properties absent from complete fbo set; typed setter ignores ffe");
    }
}

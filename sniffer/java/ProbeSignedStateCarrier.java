import java.nio.file.Files;
import java.nio.file.Path;

/** Original fyW/eZk signed carrier round-trip, without running its children. */
public final class ProbeSignedStateCarrier {
    public static void main(String[] args) throws Exception {
        if (args.length != 3) throw new IllegalArgumentException("output stateID signedLevel");
        short reference = Short.parseShort(args[1]);
        short level = Short.parseShort(args[2]);
        if (reference <= 0 || level >= 0) throw new IllegalArgumentException("positive state / negative level required");
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        fyZ.guX().a(new bbV());
        int packed = fyW.ae(reference, level);
        if (packed != ((reference << 16) + (level & 65535))
                || fyW.aar(packed) != reference || fyW.aaf(packed) != level)
            throw new AssertionError("Original signed identity packing differs");
        eZk original = eZk.a(null, ProbeStateCarrier.actor(22), null, packed);
        if (original == null || original.fQW().guI() != reference || original.fQW().cmZ() != level)
            throw new AssertionError("Original carrier lost negative state grade");
        original.f(ProbeStateCarrier.actor(-33));
        original.dg(2345);
        original.dj(1234);
        iN proto = original.bca();
        if (proto.getValue() != packed || proto.QA().getValue() != packed)
            throw new AssertionError("Original payload changed packed negative grade");
        eZk restored = new eZk();
        restored.lV(310);
        if (restored.ds(proto.toByteArray()) == null || restored.fQW() == null
                || restored.fQW().guI() != reference || restored.fQW().cmZ() != level
                || restored.LV() != 2345 || restored.bca().Qq() != 1234)
            throw new AssertionError("Original eZk decode lost signed grade or UID authority");
        Files.write(Path.of(args[0]), proto.toByteArray());
        System.out.println("PASS original fyW/eZk state=" + reference + " grade=" + level
                + " packed=" + packed + " carrier=" + restored.LV());
    }
}

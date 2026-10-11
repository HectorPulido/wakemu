import java.nio.file.*;

/** Decode the server's stele response with the installed native protobuf. */
public class VerifySteleInformation {
    public static void main(String[] args) throws Exception {
        zG value = zG.cD(Files.readAllBytes(Path.of(args[0])));
        if (!value.isInitialized() || value.azD() <= 0 || value.azG() == 0)
            throw new AssertionError("Incomplete native stele response");
        for (zC tier : value.azE()) {
            if (!tier.isInitialized()) throw new AssertionError("Incomplete native tier");
            for (zK reward : tier.ayX())
                if (!reward.isInitialized()) throw new AssertionError("Incomplete static reward");
            for (zK reward : tier.aza())
                if (!reward.isInitialized()) throw new AssertionError("Incomplete dynamic reward");
        }
        System.out.println("PASS: installed zG/zC/zK decoded selected stele, tiers and rewards");
    }
}

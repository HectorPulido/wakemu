import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;

/** Installed native pet component and cosmetic optional operand behavior. */
public final class VerifyMountSkinProjection {
    public static void main(String[] args) throws Exception {
        rw pet = new rw();
        ByteBuffer wire = ByteBuffer.wrap(Files.readAllBytes(Path.of(args[0])));
        if (!pet.aG(wire) || wire.hasRemaining() || pet.Xl == null
                || pet.Xl.Xr != Integer.parseInt(args[1]))
            throw new AssertionError("Invalid native mount skin projection");
        fC absent = fC.aw(new byte[]{8,1});
        fC zero = fC.aw(new byte[]{8,1,24,0});
        if (absent.AN() || !zero.AN() || zero.AO()!=0)
            throw new AssertionError("Accessory presence contract differs");
        System.out.println("PASS native rw/rz equipped="+pet.Xl.Xr
            +"; absent accessory differs from explicitly present zero");
    }
}

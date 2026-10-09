import java.nio.ByteBuffer;
import java.util.HexFormat;
/** Actual eZs/vJ writer, using supplied captured descriptors only. */
public final class ProbeNativeCapturedSummonCodec {
    public static void main(String[] args) {
        int index=0;
        for(String name : new String[]{"", "owned", "Baliza é"})
            for(int hp : new int[]{1, -1, 32768}) {
                eZr runner=new eZr();
                runner.rHX=0.75f; runner.rHY=1.25f;
                eHD descriptor=new eHD((short)5347,name,hp,(short)200);
                descriptor.lZ(12345L); descriptor.pX(7L);
                descriptor.M((byte)17); descriptor.a(aAS.dyD); descriptor.lE(true);
                runner.rHG=descriptor;
                runner.hwX=new SQ();runner.hwX.a(SR.values()[2]);runner.hwX.ej(7L);runner.hwX.pt(-2);
                int length=runner.rIb.zt();
                ByteBuffer output=ByteBuffer.allocate(length);runner.rIb.as(output);
                if(output.position()!=length)throw new AssertionError("length");
                System.out.println(index+++" "+HexFormat.of().formatHex(output.array()));
            }
    }
}

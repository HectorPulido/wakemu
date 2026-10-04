import java.nio.*;
import java.nio.file.*;
/** Native tA/tB decoding plus ffh/fff reconstruction of snapshot wire data. */
public class VerifySnapshotCharacteristics {
    public static void main(String[] args)throws Exception {
        ByteBuffer buffer=ByteBuffer.wrap(Files.readAllBytes(Path.of(args[0])));
        tA data=new tA();if(!data.aG(buffer)||buffer.hasRemaining())throw new AssertionError("Native characteristic decode");
        ffh stats=new ffh();if(!stats.b(data))throw new AssertionError("Native characteristic reconstruction");
        for(int[] expected:new int[][]{{1,80,120},{2,8,9},{4,3,6},{20,125,50000},{92,15,30},{97,50,2147483647}}){
            fff value=stats.e(ffw.fK((byte)expected[0]));
            if(value.aYS()!=expected[1] || value.aYU()!=expected[2])throw new AssertionError("Native PC"+expected[0]+" got "+value.aYS()+"/"+value.aYU());
            System.out.println("native stat"+expected[0]+" current"+value.aYS()+" maximum"+value.aYU());
        }
    }
}

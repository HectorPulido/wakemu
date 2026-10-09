import java.lang.reflect.Proxy;
import java.nio.file.Files;
import java.nio.file.Path;
import gnu.trove.set.hash.TByteHashSet;

/** Exhaustive QI.h mask oracle plus actual slot/exclusion/null semantics. */
public class ProbeNativeQIVisibility {
    static class Grid extends QI {
        TByteHashSet occupancy = new TByteHashSet();
        Grid() { bpZ=0; bqa=0; bqd=2; bqe=2; biD=new short[4]; biE=4; }
        @Override public TByteHashSet U(int x, int y) { return occupancy; }
    }
    static QK obstacle(boolean blocking) {
        return (QK) Proxy.newProxyInstance(QK.class.getClassLoader(), new Class<?>[]{QK.class},
            (o,m,a)->switch(m.getName()) {
                case "bcQ" -> blocking;
                case "bcN" -> (byte)0;
                default -> throw new UnsupportedOperationException(m.getName());
            });
    }
    public static void main(String[] args) throws Exception {
        Grid grid = new Grid();
        byte[] masks = new byte[65536];
        for(int raw=0; raw<65536; raw++) {
            grid.biD[0]=(short)raw;
            masks[raw]=(byte)(grid.h(0,0,(short)0)?1:0);
            if(grid.h(0,0,(short)-32768)!=grid.h(0,0,(short)32767))
                throw new AssertionError("QI.h ignores z");
        }
        Files.write(Path.of(args[0]), masks);
        grid.biD[0]=0;
        grid.biD[2]=256;
        if(!grid.h(2,0,(short)0)) throw new AssertionError("W side-coordinate alias");
        grid.biD[2]=0;
        if(grid.h(2,0,(short)0)||!grid.h(-1,0,(short)0)||!grid.h(0,2,(short)0))
            throw new AssertionError("W/index bounds");
        grid.occupancy.add((byte)0);
        if(grid.h(0,0,(short)0)) throw new AssertionError("Actual null QK");
        grid.bdI()[0]=obstacle(true);
        if(!grid.h(0,0,(short)0)) throw new AssertionError("Actual blocking QK");
        grid.d(grid.bdI()[0]);
        if(grid.h(0,0,(short)0)) throw new AssertionError("biO ignored QK");
        grid.bdM();
        if(!grid.h(0,0,(short)0)) throw new AssertionError("bdM clears exclusions");
        grid.bdI()[0]=obstacle(false);
        if(grid.h(0,0,(short)0)) throw new AssertionError("Nonblocking QK");
        System.out.println("PASS 65536 QI.h masks, W alias/bounds, z ignored, null, bcQ, biO, bdM");
    }
}

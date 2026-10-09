import java.nio.file.*;
import java.util.*;
import java.util.zip.*;

/** Real QI.i/j calls against installed VB/Vy surfaces, without a running client. */
public class ProbeNativeQISurfaces {
    static class Grid extends QI {
        Grid(VB chunk) {
            bpZ=chunk.bbn; bqa=chunk.bbo; bqd=18; bqe=18;
            biD=new short[324]; bMf.add(new VD(chunk));
        }
        void mask(int x,int y,int value) { biD[(y-bqa)*18+x-bpZ]=(short)value; }
    }
    public static void main(String[] args) throws Exception {
        int valid=0, blocked=0, mismatchedZ=0, missingIndex=0, empty=0;
        try (ZipFile archive = new ZipFile(args[0])) {
            for (var entry : Collections.list(archive.entries())) {
                if (!entry.getName().matches("-?\\d+_-?\\d+")) continue;
                aoG reader=aoG.dx(archive.getInputStream(entry).readAllBytes());
                VB chunk=VC.ag(reader.aJn()); chunk.a(reader); Grid grid=new Grid(chunk);
                for(int y=chunk.bbo;y<chunk.bbo+18;y++)for(int x=chunk.bbn;x<chunk.bbn+18;x++) {
                    Vy[] surfaces=Vy.blX(); int count=chunk.a(x,y,surfaces,0);
                    if(count>63)throw new AssertionError("surface index beyond low6 oracle domain");
                    for(int i=0;i<count;i++) {
                        grid.mask(x,y,0x100|i);
                        Vy selected=grid.i(x,y,surfaces[i].bbl);
                        if(selected==null||selected.bbl!=surfaces[i].bbl||selected.bLD!=surfaces[i].bLD)
                            throw new AssertionError("actual QI selection disagreement");
                        boolean allowed=surfaces[i].bLD!=-1;
                        if(grid.j(x,y,surfaces[i].bbl)!=allowed)throw new AssertionError("actual QI flag disagreement");
                        if(allowed)valid++;else blocked++;
                        short other=(short)(surfaces[i].bbl+1);
                        if(grid.i(x,y,other)!=null||grid.j(x,y,other))throw new AssertionError("wrong z accepted");
                        mismatchedZ++;
                    }
                    grid.mask(x,y,count);
                    if(grid.i(x,y,(short)0)!=null||grid.j(x,y,(short)0))throw new AssertionError("out-of-count index accepted");
                    missingIndex++;if(count==0)empty++;
                }
                if(grid.i(chunk.bbn-1,chunk.bbo,(short)0)!=null||grid.j(chunk.bbn-1,chunk.bbo,(short)0))
                    throw new AssertionError("out-of-bounds accepted");
            }
        }
        System.out.println("PASS actual QI.i/j valid="+valid+" blocked="+blocked+" wrong_z="+mismatchedZ+" missing_index="+missingIndex+" empty_columns="+empty);
        if(valid==0||blocked==0)throw new AssertionError("both validity branches required");
    }
}

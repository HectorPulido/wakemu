import java.nio.file.Path;

/** Export x/y territory grids from the installed native worlds.lib. */
public final class ExportNativeTerritoryCells {
    public static void main(String[] args) throws Exception {
        cdH.bla();
        String source = "jar:file:" + Path.of("client/contents/maps/data.jar")
                .toAbsolutePath() + "!/worlds.lib";
        cdH.exY().dW(source);
        for (cdI map : cdH.exY().eya()) {
            for (bMh territory : map.lVH.valueCollection()) {
                for (int encoded : territory.egx().bky().toArray()) {
                    int gridX = encoded >> 16;
                    int gridY = (short) (encoded & 0xffff);
                    System.out.println(map.lVl + "\t" + territory.d() + "\t"
                            + gridX + "\t" + gridY);
                }
            }
        }
    }
}

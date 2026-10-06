import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Read-only exporter for the native map-topology swimming bit (Vy.bml).
 * Run with the installed client jars on the classpath; this does not launch UI.
 */
public final class ExportNativeSwimmingMap {
    private static final String CHUNK_ENTRY = "-?\\d+_-?\\d+";

    public static void main(String[] args) throws Exception {
        if (args.length == 4 && args[0].equals("--all")) {
            exportAll(Path.of(args[1]), Path.of(args[2]), Path.of(args[3]));
            return;
        }
        if (args.length != 3) {
            throw new IllegalArgumentException("usage: ExportNativeSwimmingMap <map-id> <tplg-dir> <output.json> | --all <tplg-dir> <output-dir> <manifest.json>");
        }
        int mapId = Integer.parseInt(args[0]);
        MapResult result = exportMap(mapId, Path.of(args[1]), Path.of(args[2]));
        System.out.println("map=" + mapId + " chunks=" + result.chunks + " surfaces=" + result.surfaces +
                " checked=" + result.checked + " mismatches=" + result.mismatches +
                " swimming_cells=" + result.swimmingCells + " sha256=" + result.archiveSha256);
    }

    private static void exportAll(Path tplg, Path outputDirectory, Path manifest) throws Exception {
        List<Path> archives;
        try (var paths = Files.list(tplg)) {
            archives = paths.filter(p -> p.getFileName().toString().matches("\\d+\\.jar"))
                    .sorted(Comparator.comparingInt(p -> Integer.parseInt(p.getFileName().toString().replace(".jar", ""))))
                    .toList();
        }
        Files.createDirectories(outputDirectory);
        List<String> results = new ArrayList<>();
        List<String> failures = new ArrayList<>();
        int done = 0;
        for (Path archive : archives) {
            int mapId = Integer.parseInt(archive.getFileName().toString().replace(".jar", ""));
            try {
                MapResult result = exportMap(mapId, tplg, outputDirectory.resolve(mapId + ".json"));
                results.add("{\"map_id\":" + mapId + ",\"chunks\":" + result.chunks +
                        ",\"surfaces\":" + result.surfaces + ",\"checked_surfaces\":" + result.checked +
                        ",\"valid_surfaces\":" + result.validSurfaces +
                        ",\"mismatches\":" + result.mismatches + ",\"swimming_cells\":" + result.swimmingCells +
                        ",\"verified_empty\":" + result.verifiedEmpty + ",\"checked_empty_cells\":" + result.checkedEmptyCells +
                        ",\"archive_sha256\":\"" + result.archiveSha256 + "\"}");
            } catch (Throwable error) {
                failures.add("{\"map_id\":" + mapId + ",\"error\":\"" + jsonEscape(error.toString()) + "\"}");
                System.err.println("failed map=" + mapId + " error=" + error);
            }
            done++;
            if (done % 50 == 0 || done == archives.size()) {
                System.out.println("progress=" + done + "/" + archives.size() + " failures=" + failures.size());
            }
        }
        String json = "{\n  \"source\": \"installed native tplg; each surface cross-checked with VF.k after VF.g chunk load\",\n" +
                "  \"installed_archive_count\": " + archives.size() + ",\n" +
                "  \"verified_map_count\": " + results.size() + ",\n" +
                "  \"failed_map_count\": " + failures.size() + ",\n" +
                "  \"installed_map_ids\": [" + joinMapIds(archives) + "],\n" +
                "  \"verified_map_ids\": [" + joinResultMapIds(results) + "],\n" +
                "  \"unverified_map_ids\": [" + joinFailureMapIds(failures) + "],\n" +
                "  \"maps\": [" + String.join(",", results) + "],\n" +
                "  \"failures\": [" + String.join(",", failures) + "]\n}\n";
        Files.createDirectories(manifest.toAbsolutePath().getParent());
        Files.writeString(manifest, json, StandardCharsets.UTF_8);
        System.out.println("manifest=" + manifest + " verified=" + results.size() + " failures=" + failures.size());
        if (!failures.isEmpty()) throw new IllegalStateException("partial topology export; inspect manifest failures");
    }

    private static MapResult exportMap(int mapId, Path tplgPath, Path output) throws Exception {
        Path tplg = tplgPath.toAbsolutePath();
        Path archive = tplg.resolve(mapId + ".jar");
        if (!Files.isRegularFile(archive)) throw new IllegalArgumentException("missing topology archive: " + archive);

        // Avoid retaining topology caches across maps; all reads remain local/offline.
        VF.reset();
        VF.dd("jar:file:" + tplg + "/%d.jar!/");
        VF.fs(mapId);
        List<String> cells = new ArrayList<>();
        int surfaces = 0;
        int validSurfaces = 0;
        int checked = 0;
        int mismatches = 0;
        int chunks = 0;
        List<Long> emptyCellCoordinates = new ArrayList<>();
        try (ZipFile zip = new ZipFile(archive.toFile())) {
            for (ZipEntry entry : Collections.list(zip.entries())) {
                if (!entry.getName().matches(CHUNK_ENTRY)) continue;
                chunks++;
                aoG resource;
                try (var in = zip.getInputStream(entry)) {
                    resource = aoG.dx(in.readAllBytes());
                }
                VB chunk = VC.ag(resource.aJn());
                if (chunk == null) throw new IllegalStateException("unknown topology chunk codec: " + entry.getName());
                chunk.a(resource);
                int minX = chunk.bbn;
                int minY = chunk.bbo;
                // VF.k only consults loaded topology. Load this exact chunk through VF first.
                VF.g((short) Ve.qb(minX), (short) Ve.qc(minY));
                for (int x = minX; x < minX + 18; x++) {
                    for (int y = minY; y < minY + 18; y++) {
                        Vy[] column = Vy.blX();
                        int count = chunk.a(x, y, column, 0);
                        if (count == 0 && surfaces == 0) {
                            emptyCellCoordinates.add((((long) x) << 32) | (y & 0xffffffffL));
                        }
                        for (int i = 0; i < count; i++) {
                            Vy surface = column[i];
                            boolean firstAtHeight = true;
                            for (int j = 0; j < i; j++) {
                                if (column[j].bbl == surface.bbl) {
                                    firstAtHeight = false;
                                    break;
                                }
                            }
                            if (!firstAtHeight) continue;
                            surfaces++;
                            if (surfaces == 1) emptyCellCoordinates.clear();
                            boolean nativeBit = false;
                            for (int j = i; j < count; j++) {
                                if (column[j].bbl == surface.bbl && column[j].bml()) {
                                    nativeBit = true;
                                    break;
                                }
                            }
                            // The native VF.k implementation checks z+bit, without filtering bLD.
                            boolean nativeVF = VF.k(x, y, surface.bbl);
                            checked++;
                            if (nativeVF != nativeBit) {
                                if (mismatches < 8) System.err.println("mismatch x=" + x + " y=" + y + " z=" + surface.bbl +
                                        " bit=" + nativeBit + " flags=" + surface.bLF + " VF=" + nativeVF +
                                        " chunk=" + entry.getName() + " origin=" + minX + "," + minY);
                                mismatches++;
                            }
                            if (nativeBit) cells.add("[" + x + "," + y + "," + surface.bbl + "]");
                        }
                        for (int i = 0; i < count; i++) if (column[i].bLD >= 0) validSurfaces++;
                    }
                }
            }
        }
        boolean verifiedEmpty = surfaces == 0;
        int checkedEmptyCells = 0;
        if (verifiedEmpty) {
            if (chunks == 0 || emptyCellCoordinates.size() != chunks * 18 * 18)
                throw new IllegalStateException("no complete native topology cells to prove empty");
            // Vy.bbl is a signed short. With no Vy records, no z can match; probe both
            // representable bounds and zero through the real native VF.k path at every cell.
            for (long packed : emptyCellCoordinates) {
                int x = (int) (packed >> 32);
                int y = (int) packed;
                if (VF.k(x, y, Short.MIN_VALUE) || VF.k(x, y, 0) || VF.k(x, y, Short.MAX_VALUE))
                    mismatches++;
                checkedEmptyCells++;
            }
        }
        if (mismatches != 0) throw new IllegalStateException("VF.k vs Vy.bml mismatches: " + mismatches + "/" + checked);
        Collections.sort(cells);
        String json = "{\n" +
                "  \"source\": \"installed native tplg topology; VF.k == Vy.bml == (Vy.bLF & 512) != 0\",\n" +
                "  \"map_id\": " + mapId + ",\n" +
                "  \"archive_sha256\": \"" + sha256(archive) + "\",\n" +
                "  \"surface_count\": " + surfaces + ",\n" +
                "  \"valid_surface_count\": " + validSurfaces + ",\n" +
                "  \"native_vf_validation\": {\"checked_surfaces\": " + checked + ", \"mismatches\": " + mismatches +
                ", \"verified_empty\": " + verifiedEmpty + ", \"checked_chunks\": " + (verifiedEmpty ? chunks : 0) +
                ", \"checked_empty_cells\": " + checkedEmptyCells +
                ", \"empty_probe_z\": [" + Short.MIN_VALUE + ",0," + Short.MAX_VALUE + "]},\n" +
                "  \"swimming_cells_xyz\": [" + String.join(",", cells) + "]\n" +
                "}\n";
        Files.createDirectories(output.toAbsolutePath().getParent());
        Files.writeString(output, json, StandardCharsets.UTF_8);
        return new MapResult(chunks, surfaces, checked, mismatches, validSurfaces, cells.size(), verifiedEmpty, checkedEmptyCells, sha256(archive));
    }

    private record MapResult(int chunks, int surfaces, int checked, int mismatches, int validSurfaces, int swimmingCells, boolean verifiedEmpty, int checkedEmptyCells, String archiveSha256) {}

    private static String jsonEscape(String value) {
        return value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r");
    }

    private static String joinMapIds(List<Path> paths) {
        return paths.stream().map(p -> p.getFileName().toString().replace(".jar", ""))
                .collect(java.util.stream.Collectors.joining(","));
    }

    private static String joinResultMapIds(List<String> rows) {
        return rows.stream().map(row -> row.substring(row.indexOf(":") + 1, row.indexOf(",")))
                .collect(java.util.stream.Collectors.joining(","));
    }

    private static String joinFailureMapIds(List<String> rows) {
        return rows.stream().map(row -> row.substring(row.indexOf(":") + 1, row.indexOf(",")))
                .collect(java.util.stream.Collectors.joining(","));
    }

    private static String sha256(Path path) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (var in = Files.newInputStream(path)) {
            byte[] buffer = new byte[65536];
            for (int n; (n = in.read(buffer)) >= 0;) digest.update(buffer, 0, n);
        }
        return HexFormat.of().formatHex(digest.digest());
    }
}

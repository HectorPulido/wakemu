import com.google.gson.Gson;
import java.nio.file.*;
import java.util.*;

/** eJy.tt is the native alias resolver shared by current/max/percent predicates. */
public class ExportCharacteristicConditionAliases {
    public static void main(String[] args) throws Exception {
        Set<String> candidates=new TreeSet<>(Files.readAllLines(Path.of(args[0])));
        // Preserve the non-ASCII eJy.tt branch that ASCII candidate scans omit.
        // The original resolver still decides whether the alias exists.
        candidates.add("contrôle");
        for(ffw stat:ffw.values()) candidates.add(stat.toString());
        Map<String,Object> aliases=new TreeMap<>();
        for(String candidate:candidates) {
            ffw stat=eJy.tt(candidate);
            if(stat!=null) aliases.put(candidate.toUpperCase(Locale.ROOT),Map.of("id",stat.aKg()&255,"name",stat.toString()));
        }
        Files.writeString(Path.of(args[1]),new Gson().toJson(Map.of("source","Installed native eJy.tt resolver; ffw.values and native eJy string constants","aliases",aliases)));
        System.out.println("Exported native characteristic aliases: "+aliases.size());
    }
}

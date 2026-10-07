import java.nio.file.Path;
import java.util.*;

/**
 * Offline export of the exact client evaluation inputs used by fpN.y(fnO).
 * This only reads installed client data; it does not touch a game account.
 */
public final class ExportNativeShardBonuses {
  private static String q(String value) {
    return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
  }

  private static void ints(int[] values) {
    System.out.print("[");
    for (int i = 0; i < values.length; i++) {
      if (i != 0) System.out.print(",");
      System.out.print(values[i]);
    }
    System.out.print("]");
  }

  public static void main(String[] args) throws Exception {
    apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
    System.out.print("{\"source\":{\"client_jar\":\"client/lib/wakfu-client.jar\",\"client_jar_sha256\":\"e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd\",\"mechanism\":\"fpN.y(fnO), eVn.a(level), fpG.WA(slotLevel), fpG.gjC()\",\"family_semantics\":\"equipment family enum names; matching fpG.gjC() doubles effect value and secondary\",\"note\":\"Raw native values, no server operation policy inferred\"},\"items\":[");
    boolean[] firstItem = {true};
    apw.bGL().a(new aLO(), new apB<aLO>() {
      @Override public void load(aLO raw) {
        try {
          bJp item = new bIJ().f(raw);
          if (item.dLn() == null || item.gjg() == null) return;
          fpG profile = item.dYo();
          if (profile == null) return;
          List<eVn> effects = new ArrayList<>();
          item.gjg().forEachRemaining(effects::add);
          if (effects.isEmpty()) return;

          if (!firstItem[0]) System.out.print(",");
          firstItem[0] = false;
          QE nativeColor = profile.dFX();
          if (nativeColor == null) throw new IllegalStateException("Native shard color missing");
          System.out.print("{\"reference\":" + item.d() + ",\"item_level\":" + item.cmZ()
              + ",\"native_bonus_color\":{\"name\":" + q(nativeColor.name())
              + ",\"ordinal\":" + nativeColor.ordinal() + "},\"selectable\":" + !profile.gjB()
              + ",\"shard_count_by_level\":[");
          for (int level = 1; level <= profile.Fq(); level++) {
            if (level != 1) System.out.print(",");
            System.out.print(profile.Wz(level));
          }
          System.out.print("],\"minimum_player_level_by_bonus_level\":[");
          int[] levelUnlocks = profile.gjD();
          for (int level = 1; level <= levelUnlocks.length; level++) {
            if (level != 1) System.out.print(",");
            System.out.print(levelUnlocks[level - 1]);
          }
          System.out.print("],\"equipment_families\":[");
          boolean firstFamily = true;
          List<fnO> families = new ArrayList<>(profile.gjC());
          families.sort(Comparator.comparingInt(fnO::aKg));
          for (fnO family : families) {
            if (!firstFamily) System.out.print(",");
            firstFamily = false;
            System.out.print("{\"native_name\":" + q(family.name()) + ",\"native_id\":" + family.aKg() + "}");
          }
          System.out.print("],\"slot_level_map\":[");
          int maxInput = Math.max(0, profile.Wz(profile.Fq()));
          List<Integer> effectiveLevels = new ArrayList<>();
          int previous = Integer.MIN_VALUE;
          for (int slotLevel = 0; slotLevel <= maxInput; slotLevel++) {
            int effectiveLevel = profile.WA(slotLevel);
            if (effectiveLevel != previous) {
              if (!effectiveLevels.isEmpty()) System.out.print(",");
              effectiveLevels.add(effectiveLevel);
              System.out.print("{\"slot_level\":" + slotLevel + ",\"effective_level\":" + effectiveLevel + "}");
              previous = effectiveLevel;
            }
          }
          System.out.print("],\"effects\":[");
          boolean firstEffect = true;
          for (eVn effect : effects) {
            if (!firstEffect) System.out.print(",");
            firstEffect = false;
            Object runner = eVi.fLJ().pS(effect.awM());
            PC stat = null;
            if (runner instanceof eWN n) stat = n.fNI();
            else if (runner instanceof eWW n) stat = n.fNI();
            System.out.print("{\"id\":" + effect.aZE() + ",\"generic\":" + effect.awM() + ",\"runner\":" + q(runner == null ? "" : runner.getClass().getName())
                + ",\"stat_id\":" + (stat == null ? -1 : (stat.aKg() & 255)) + ",\"parameter_count\":" + effect.fKJ()
                + ",\"effect_max_level\":" + effect.fKS() + ",\"effect_min_level\":" + effect.fKR()
                + ",\"has_triggers\":" + (effect.fKV().hasNext() || effect.fKW().hasNext()) + ",\"target_mask\":" + effect.aZR()
                + ",\"effect_criteria\":" + (effect.fKT() != null) + ",\"levels\":[");
            boolean firstLevel = true;
            for (int effectiveLevel : effectiveLevels) {
              // fpN.y applies rows when fKR <= effectiveLevel <= fKS.
              boolean active = effectiveLevel >= effect.fKR() && effectiveLevel <= effect.fKS();
              if (!active) continue;
              if (!firstLevel) System.out.print(",");
              firstLevel = false;
              System.out.print("{\"effective_level\":" + effectiveLevel + ",\"values\":[");
              for (int index = 0; index < effect.fKI().length / 2; index++) {
                if (index != 0) System.out.print(",");
                System.out.print(effect.a(index, (short) effectiveLevel, eVh.rpA));
              }
              System.out.print("]}");
            }
            System.out.print("]}");
          }
          System.out.print("]}");
        } catch (Throwable failure) {
          System.err.println("Skipped native item " + raw.d() + ": " + failure.getClass().getSimpleName());
        }
      }
    });
    System.out.println("]}");
  }
}

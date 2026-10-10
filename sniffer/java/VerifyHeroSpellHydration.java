import java.nio.*;
import java.nio.file.*;
import java.util.*;
/** Native owned-hero format10 spellbook/deck and repeated component refresh. */
public final class VerifyHeroSpellHydration {
    public static void main(String[] args) throws Exception {
        try {
            apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
            java.util.List<biB> owned = new ArrayList<>();
            Set<Integer> previous = null;
            for (String file : args) {
                cue packet = new cue(); packet.dp(Files.readAllBytes(Path.of(file)));
                byte[] entity = packet.eGo();
                eHk raw = new eHk(); raw.ew(entity);
                if (entity[0] != 10) throw new AssertionError("owned actor must use format10");
                if (raw.fsQ().VY == null || raw.fsQ().VY.isBlank()
                    || raw.fsT().SC <= 0 || raw.fvh().Su.length == 0)
                    throw new AssertionError("missing owned name/breed/appearance");
                Set<Integer> spells = new TreeSet<>();
                for (yD record : raw.fvG().Zc.ams) {
                    yy spell = record.amt;
                    if ((spell.aaq >>> 32) != raw.fsS().Vc)
                        throw new AssertionError("wrong spell UID owner");
                    spells.add(spell.amm);
                }
                fzh decks = fzg.gE(ByteBuffer.wrap(raw.fwi().TM));
                if (spells.isEmpty() || decks.gvf().isEmpty())
                    throw new AssertionError("missing spellbook/decks");
                for (fzf deck : decks.gvf().values()) {
                    for (int reference : deck.eNR())
                        if (reference != 0 && !spells.contains(reference))
                            throw new AssertionError("active deck contains foreign spell");
                    for (int reference : deck.eNS())
                        if (reference != 0 && !spells.contains(reference))
                            throw new AssertionError("passive deck contains foreign spell");
                }
                biB actor = new biB(false);
                actor.dtj().a(actor.dtj().fsS(), entity);
                actor.dtj().a(actor.dtj().fsR(), entity);
                fkK.suH.d(raw.fsR().Vh, actor);
                fkK.suH.ay(raw.fsR().Vh, raw.fsS().Vc);
                owned.add(actor);
                for (int repeat = 0; repeat < 2; repeat++) {
                    actor.dtj().a(actor.dtj().fwa(), entity);
                    if (bdF.hHU.jf(actor.Sn()) == null)
                        throw new AssertionError("native achievements registry missing before aQc");
                    actor.dtj().a(actor.dtj().fsQ(), entity);
                    if (!actor.getName().equals(raw.fsQ().VY))
                        throw new AssertionError("native name consumer loses name");
                    actor.dtj().a(actor.dtj().fvG(), entity);
                    actor.dtj().a(actor.dtj().fwi(), entity);
                    if (actor.dok().aWk() != spells.size())
                        throw new AssertionError("native spellbook consumer loses entries: " + actor.dok().aWk());
                    if (!actor.drp().gvf().keySet().equals(decks.gvf().keySet()))
                        throw new AssertionError("native deck consumer loses build indices");
                }
                System.out.println("PASS actor=" + raw.fsS().Vc + " format10 spells="
                    + spells.size() + " deck builds=" + decks.gvf().keySet()
                    + " actual biS/biR consumers refreshed twice");
                if (previous != null && previous.equals(spells))
                    throw new AssertionError("different class fixtures have identical spellbooks");
                previous = spells;
            }
            for (int round = 0; round < 3; round++) {
                for (biB actor : owned) {
                    fkJ.suE.av(actor.Xi(), actor.Sn());
                    biB selected = fkK.suH.aA(actor.Xi(), fkJ.suE.sS(actor.Xi()));
                    if (selected != actor || selected.dok().aWk() == 0
                        || selected.drp().gvf().isEmpty())
                        throw new AssertionError("selected owned registry loses book/deck");
                }
            }
            System.out.println("PASS repeated native owned-registry selection preserves each actor spellbook/deck");
            System.exit(0);
        } catch (Throwable error) { error.printStackTrace(); System.exit(1); }
    }
}

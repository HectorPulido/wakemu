import java.lang.reflect.Proxy;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

/** Original logical displacement callbacks with original eGj carried partners. */
public final class VerifyPilotCarrierDisplacementQueue {
    public static void main(String[] args) throws Exception {
        var unsafe = VerifyPilotDisplacementQueue.setup();
        // The captured handler entry contains an existing logical pair, not a
        // carry cast/group registration. Original eXD consults this native
        // manager even when eWB has no associated release group (id zero).
        // Initialize the original empty manager; retain its original lookup.
        fyE.a(new fyE<fyD>() {});
        apw.bGL().dd("jar:file:" + Path.of(args[3]).toAbsolutePath() + "/%d.jar!/%d.bin");
        Map<Long,VerifyPilotCarryQueue.Actor> actors = new LinkedHashMap<>();
        Map<Long,Long> partners = new LinkedHashMap<>();
        for (String line : Files.readAllLines(Path.of(args[2]))) {
            String[] values = line.split("\\t");
            VerifyCombatReconstructionSlice.check(values.length == 5, "explicit actor row");
            long id = Long.parseLong(values[0]);
            VerifyCombatReconstructionSlice.check(!actors.containsKey(id), "unique actor identity");
            actors.put(id, VerifyPilotCarryQueue.actor(unsafe, id, new int[]{
                Integer.parseInt(values[1]), Integer.parseInt(values[2]), Integer.parseInt(values[3])}));
            if (!values[4].equals("null")) partners.put(id, Long.parseLong(values[4]));
        }
        for (var relation : partners.entrySet()) {
            VerifyCombatReconstructionSlice.check(actors.containsKey(relation.getValue()), "registered carried partner");
            VerifyCombatReconstructionSlice.check(actors.get(relation.getKey()).a(
                (eHH)actors.get(relation.getValue())), "original eGj carry setup");
        }
        var initial = VerifyPilotCarryQueue.view(actors);
        cvX packet = new cvX();
        VerifyCombatReconstructionSlice.check(packet.dp(Files.readAllBytes(Path.of(args[0]))), "exact displacement decode");
        iN wire = iN.bf(packet.eIJ());
        PW registry = (PW)Proxy.newProxyInstance(PW.class.getClassLoader(), new Class[]{PW.class},
            (p,m,a)->m.getName().equals("de") ? actors.get((Long)a[0]) : null);
        var grid = new VerifyCombatReconstructionSlice.Grid();
        PN context = (PN)Proxy.newProxyInstance(PN.class.getClassLoader(), new Class[]{PN.class},
            (p,m,a)->switch(m.getName()) {
                case "bae" -> registry;
                case "bad" -> grid;
                case "baf", "baa" -> null;
                default -> m.invoke(bcz.dcW(), a);
            });
        eZR runner = (eZR)eVi.fLJ().pS(packet.eII()).b(context);
        VerifyCombatReconstructionSlice.check(runner.ds(packet.eIJ()) != null && runner.baZ() != null
            && ((eVn)runner.baZ()).aZE() == wire.Qs(), "exact original definition/hydration");
        var action = new VerifyPilotCarryQueue.Application(packet, runner, actors, context);
        action.cYb(); action.iD(wire.Qw()); if (wire.Qx()) action.fe(wire.Qy());
        aER queue = new aER(); queue.c(action); queue.cbu();
        VerifyCombatReconstructionSlice.check(action.completed && queue.cbt().isEmpty(), "original callback/FIFO completed");
        VerifyCombatReconstructionSlice.check(VerifyPilotDisplacementQueue.errors.get() == 0, "no swallowed native error");
        var output = new LinkedHashMap<String,Object>();
        output.put("completed_normally", true); output.put("opcode", 12613);
        output.put("family", packet.eII()); output.put("action_id", packet.cbc());
        output.put("generic_effect", wire.Qs()); output.put("uid", wire.LV());
        output.put("caster", wire.Qw()); output.put("target", wire.Qy());
        output.put("before", initial); output.put("after", VerifyPilotCarryQueue.view(actors));
        output.put("native_completed_action_ids", new int[]{packet.cbc()}); output.put("queue_drained", true);
        output.put("scope", "original eGj carry setup and displacement/implicit partner callbacks; renderer parenting and visual scripts skipped");
        Files.writeString(Path.of(args[1]), VerifyCombatReconstructionSlice.json(output) + "\n");
        System.out.println("PASS original native carrier displacement callback/FIFO");
        System.exit(0);
    }
}

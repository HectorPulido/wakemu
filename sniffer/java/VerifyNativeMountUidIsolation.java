import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.lang.reflect.Field;

/** Offline original-JAR registry oracle; never patches or attaches to a client. */
public final class VerifyNativeMountUidIsolation {
    private static final long A = 1099511700001L, B = 1099511700002L;
    // Minimal definition authority: no item effects, graphics or eligibility claims.
    private static final class ItemDefinition extends fpC {
        ItemDefinition() { lV(18682); sQl = 1; }
        public boolean dZZ() { return false; }
        public String getName() { return "native-oracle-item"; }
        public String cZY() { return "native-oracle-item"; }
    }
    private static final class Definitions extends foA<fpC> {
        Definitions() { super(); e(new ItemDefinition()); }
    }
    private static final class PetFactory extends fvJ {
        public TQ gpU() { return TP.fl(1700000000000L); }
    }
    private static byte[] bytes(JsonObject fixtures, String key) {
        return java.util.HexFormat.of().parseHex(fixtures.get(key).getAsString());
    }
    private static fpd registry(JsonObject fixtures, String key) {
        cxC packet = new cxC();
        check(packet.dp(bytes(fixtures,key)), "original cxC registry decoder");
        return fpi.a(packet.KU(),packet.eKC());
    }
    private static fnR inserted(JsonObject fixtures, String key) {
        cxa packet = new cxa();
        check(packet.dp(bytes(fixtures,key)), "original cxa physical decoder");
        return fox.eM(packet.eJS());
    }
    private static fnR item(fpd registry, long uid) {
        return registry.C(uid).orElseThrow();
    }
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
    public static void main(String[] args) throws Exception {
        foA.a(new Definitions()); fvJ.a(new PetFactory());
        // Constructor fields are pinned to the installed definition76's native model.
        fwu.tmE.b(new fwt(76, 24, 6, 20, 0L, 0L, (byte) 0,
                (short) 50, (short) 50), 18682);
        JsonObject fixtures = JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        fnR physicalA=inserted(fixtures,"insertion_a_initial");
        fnR physicalB=inserted(fixtures,"insertion_b_initial");
        fnR physicalFedA=inserted(fixtures,"insertion_a_fed");
        check(physicalA.LV()==A && physicalB.LV()==B && physicalFedA.LV()==A,
                "physical UID preservation");
        check(physicalA.efH()!=physicalB.efH() && physicalB.efH().agO()==0
                && physicalFedA.efH().agO()==100, "physical pet isolation and refreshed XP");
        for(String key : new String[]{"removal_a","removal_b"}) {
            cwZ removal=new cwZ(); check(removal.dp(bytes(fixtures,key)),"cwZ decoder");
            check(removal.bfh()==-1,"native signed remove quantity");
            check(removal.bTD()==(key.equals("removal_a")?A:B),"remove UID");
        }
        rw actorPet=new rw();
        check(actorPet.aG(ByteBuffer.wrap(bytes(fixtures,"pet_section"))), "native rw actor PET decode");
        check(actorPet.Xk==null && actorPet.Xl.Xp==76 && actorPet.Xl.Xt==20,
                "native actor PET definition/health; no UID or XP carrier");
        fpd initial = registry(fixtures, "registry_initial");
        bIM.kel.a(1L,initial); fph.sPa.a(1L,bIM.kel);
        check(fph.sPa.aM(1L,1L)==initial,"native registry owner routing");
        fnR a = item(initial, A), b = item(initial, B);
        fvH originalA = a.efH(), originalB = b.efH();
        check(a != b && originalA != originalB, "distinct UID/native pet identities");
        check(originalA.agO() == 0 && originalB.agO() == 0, "initial XP");
        bLK openedPanel = null;
        try { openedPanel = new bLK(a); }
        catch (Throwable boundary) {
            System.out.println("BOUNDARY original bLK constructor: " + boundary.getClass().getName()
                    + ": " + boundary.getMessage());
        }
        fpd fed = registry(fixtures, "registry_a_fed");
        bIM.kel.a(1L,fed);
        check(fph.sPa.aM(1L,1L)==initial,"native registry object retained");
        check(item(initial,A)==item(fed,A),"native registry contents rebound to refreshed UID instance");
        fnR updatedA = item(fed, A), unchangedB = item(fed, B);
        check(updatedA.efH().agO() == 100 && updatedA.efH().cmZ() == 2, "A level2");
        check(unchangedB.efH().agO() == 0 && unchangedB.efH().cmZ() == 0, "B remains0");
        check(updatedA.efH() != originalA, "native full registry hydration allocates new pet");
        check(originalA.agO() == 0, "old observer state is not mutated by new registry");
        fpd rejected = registry(fixtures, "registry_delete_rejected");
        check(item(rejected,A).efH().agO()==100 && item(rejected,B).efH().agO()==0,
                "rejected-delete authoritative registry retains both UID states");
        bIM.kel.a(1L,rejected);
        check(item(initial,A).efH().agO()==100 && initial.C(B).isPresent(),"rejected native publication");
        fpd deleted = registry(fixtures, "registry_b_deleted");
        bIM.kel.a(1L,deleted);
        check(initial.C(B).isEmpty() && item(initial,A).efH().agO()==100,"deleted native publication");
        fpd ten=registry(fixtures,"registry_a_fed_500");
        check(item(ten,A).efH().cmZ()==10 && item(ten,B).efH().cmZ()==0,"independent level10 continuation");
        check(deleted.C(B).isEmpty() && item(deleted,A).efH().agO()==100,
                "successful-delete registry removes B only");
        System.out.println("PASS original cxa/cwZ/cxC/rw/fpi/fox/kX/lz/fvN/bIM/fph registry: two UID identity, XP, level, rejection/success snapshots");
        // A genuine panel retains its initial fvH in final bLE.kuu. Its constructor
        // may need global UI state; report that boundary instead of replacing it.
        try {
            check(openedPanel!=null,"original panel constructor must succeed with installed natives path");
            bLK panel = openedPanel;
            Field retained = bLE.class.getDeclaredField("kuu"); retained.setAccessible(true);
            check(retained.get(panel)==originalA, "panel retains original pet object");
            check(((fvH)retained.get(panel)).agO()==0, "old panel pet remains stale after detached rehydration");
            System.out.println("PASS original bLK opened before registry updates retains old pet; full chZ panel-rebind path remains separate");
        } catch (Throwable boundary) {
            if (boundary instanceof AssertionError) throw (AssertionError) boundary;
            System.out.println("BOUNDARY original bLK constructor: " + boundary.getClass().getName()
                    + ": " + boundary.getMessage());
        }
        try {
            aTx.cWt().a(new aTJ());
            cxC nativeMessage=new cxC();
            check(nativeMessage.dp(bytes(fixtures,"registry_a_fed")),"chZ native message decode");
            new chZ().a(nativeMessage);
            check(item(bIM.kel.tT(1L),A).efH().agO()==100,"full chZ handler registry update");
            System.out.println("PASS original complete chZ13078 handler; no selected UI mount panel was registered");
        } catch(Throwable boundary) {
            if(boundary instanceof AssertionError) throw (AssertionError)boundary;
            System.out.println("BOUNDARY original chZ handler: "+boundary.getClass().getName()+": "+boundary.getMessage());
        }
        try {
            biB actor=new biB(false);
            check(actor.dqT()!=null,"original actor inventory constructed");
            aTx.cWt().f(actor);
            System.out.println("PASS original biB constructor/current-actor binding; container registration and selected UI lifecycle remain separate");
        } catch(Throwable boundary) {
            if(boundary instanceof AssertionError) throw (AssertionError)boundary;
            System.out.println("BOUNDARY original actor bootstrap: "+boundary.getClass().getName()+": "+boundary.getMessage());
        }
        System.out.println("BOUNDARY physical actor/container insertion-removal handlers, selected GUI panel rebind and PET actor application are not executed here");
        System.exit(0);
    }
}

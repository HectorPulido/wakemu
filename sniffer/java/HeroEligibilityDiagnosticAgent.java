import java.lang.instrument.Instrumentation;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.swing.SwingUtilities;
import java.util.Map;
import java.util.List;
import java.util.LinkedHashMap;
import java.util.ArrayList;

/** Read-only diagnostic of the actual native hero UI eligibility inputs. */
public class HeroEligibilityDiagnosticAgent {
    /** Invoke on the native UI thread; never activates actors or sends packets. */
    public static Map<String,Object> diagnostic() {
        Map<String,Object> result = new LinkedHashMap<>();
        try {
            long account = bdB.xl();
            result.put("account", account);
            java.util.Optional<eDN> component = eDP.foL().a(account, eDS.oUl);
            result.put("company_present", component.isPresent());
            if (component.orElse(null) instanceof eSJ company) {
                result.put("company_account", company.xl());
                result.put("company_chief", company.dyK());
                result.put("company_nation", company.Xt());
                result.put("company_guild", company.Ya());
                result.put("company_activated", company.aPU());
            }
            biB main = aTx.cWt().cWu();
            if (main != null) {
                result.put("main_actor", main.Sn());
                result.put("main_nation", main.Xt());
                result.put("main_guild", main.Ya());
                result.put("main_party_listeners", listenerNames(main.drw(), "jCR"));
                fgq group = main.drw().dQa();
                if (group != null) {
                    result.put("party_id", group.Sn());
                    result.put("party_listeners", listenerNames(group, "ski"));
                    List<Map<String,Object>> members = new ArrayList<>();
                    group.gay().forEachValue(member -> {
                        Map<String,Object> row = new LinkedHashMap<>();
                        row.put("actor_id", member.KU());
                        row.put("account_id", member.cBt());
                        row.put("hero", member.dpL());
                        row.put("name", member.getName());
                        bit cached = cZT.ofW.oK(member.KU());
                        row.put("cached_row", cached != null);
                        row.put("cached_actor_matches_owned", cached != null && cached.dgD() == fkK.suH.sY(member.KU()));
                        members.add(row);
                        return true;
                    });
                    result.put("party_members", members);
                }
            }
            Map<String,Object> slots = new LinkedHashMap<>();
            for (String name : new String[]{"iBF", "iBG", "iBH"}) {
                java.lang.reflect.Field field = bns.class.getDeclaredField(name);
                field.setAccessible(true);
                bit row = ((bnr) field.get(bns.iBL)).dyy();
                slots.put(name, row == null ? null : row.dgD().Sn());
            }
            result.put("hero_slots", slots);
            List<Map<String,Object>> roster = new ArrayList<>();
            result.put("roster", roster);
            for (big actor : biz.dpY().dqe()) {
                Map<String,Object> row = new LinkedHashMap<>();
                roster.add(row);
                row.put("actor_id", actor.Sn());
                row.put("class", actor.getClass().getName());
                row.put("header_owner", actor.Xi());
                row.put("company_owner", actor.cBt());
                row.put("nation", actor.Xt());
                row.put("cached_nation", biz.dpY().an(actor));
                row.put("guild", actor.Ya());
                if (actor instanceof bjo) {
                    bit nativeRow = new bit(actor, null);
                    for (String field : new String[]{"isInCompanyNation", "isInCompanyGuild", "canAddToParty", "addToPartyError"})
                        row.put(field, nativeRow.eH(field));
                }
            }
        } catch (Throwable error) {
            result.put("error", error.toString());
        }
        return result;
    }
    private static List<String> listenerNames(Object owner, String name) throws Exception {
        java.lang.reflect.Field field = owner.getClass().getDeclaredField(name);
        field.setAccessible(true);
        List<String> result = new ArrayList<>();
        for (Object listener : (Iterable<?>) field.get(owner)) result.add(listener.getClass().getName());
        return result;
    }
    public static void agentmain(String output, Instrumentation ignored) throws Exception {
        StringBuilder result = new StringBuilder();
        SwingUtilities.invokeAndWait(() -> {
            try {
                result.append("native_ui_state=").append(diagnostic()).append('\n');
                long account = bdB.xl();
                result.append("account=").append(account)
                        .append(" company=").append(eDP.foL().a(account, eDS.oUl))
                        .append('\n');
                biB main = aTx.cWt().cWu();
                if (main != null) {
                    result.append("main=").append(main.Sn()).append(" nation=")
                            .append(main.Xt()).append(" guild=").append(main.Ya()).append('\n');
                }
                for (big actor : biz.dpY().dqe()) {
                    result.append("roster=").append(actor.Sn()).append(" class=")
                            .append(actor.getClass().getName()).append(" headerOwner=")
                            .append(actor.Xi()).append(" companyOwner=").append(actor.cBt())
                            .append(" nation=").append(actor.Xt()).append(" cachedNation=")
                            .append(biz.dpY().an(actor)).append(" guild=").append(actor.Ya());
                    if (actor instanceof bjo) {
                        bit row = new bit(actor, null);
                        result.append(" UI_nation=").append(row.eH("isInCompanyNation"))
                                .append(" UI_guild=").append(row.eH("isInCompanyGuild"))
                                .append(" UI_canAdd=").append(row.eH("canAddToParty"))
                                .append(" UI_error=").append(row.eH("addToPartyError"));
                    }
                    result.append('\n');
                }
            } catch (Throwable error) {
                result.append(error);
                for (StackTraceElement line : error.getStackTrace()) result.append('\n').append(line);
            }
        });
        Files.writeString(Path.of(output), result.toString());
    }
}

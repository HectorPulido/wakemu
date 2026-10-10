import java.lang.instrument.Instrumentation;
import java.nio.file.*;
import java.util.*;
import javax.swing.SwingUtilities;
import com.google.gson.Gson;
/** Read-only native eligibility inspection. Never executes an item action. */
public class ItemUseDiagnosticAgent {
 public static Map<String,Object> diagnostic() {
  Map<String,Object> result=new LinkedHashMap<>();
  try {
   biB local=aTx.cWt().cWu();
   if(local==null){result.put("player_present",false);return result;}
   result.put("actor_id",local.Sn());result.put("ownership_key",local.Xi());
   result.put("account_key",aTx.cWt().cWy().xl());
   result.put("local_identity",System.identityHashCode(local));
   List<Map<String,Object>> registered=new ArrayList<>();
   for(long key:new long[]{local.Xi(),aTx.cWt().cWy().xl()}) {
    for(long id:fkK.suH.sZ(key).toArray()) {
     eGj actor=fkK.suH.sY(id);
     Map<String,Object> value=new LinkedHashMap<>();
     value.put("key",key);value.put("actor_id",id);
     value.put("identity",actor==null?null:System.identityHashCode(actor));
     value.put("same_as_local",actor==local);
     registered.add(value);
    }
   }
   result.put("registered_owners",registered);
   result.put("selected_actor",bxY.dQA()==null?null:bxY.dQA().Sn());
   List<Map<String,Object>> items=new ArrayList<>();
   local.drK().K(item->{
    Map<String,Object> row=new LinkedHashMap<>();row.put("uid",item.LV());row.put("reference",item.awe());
    try {
     if(!(item.dTv().gfJ() instanceof bHu action))return true;
     row.put("action_class",action.getClass().getName());
     eGj owner=fkH.ak(local.Xi(),item.LV());
     row.put("owner_actor",owner==null?null:owner.Sn());
     row.put("account_owner_found",fkH.ag(aTx.cWt().cWy().xl(),item.LV())!=null);
     row.put("available",item.aqb());row.put("usable",item.fKQ());
     row.put("item_level",item.cmZ());row.put("player_level",local.cmZ());
     row.put("item_use_criterion",String.valueOf(item.dTv().a(fnE.sGD)));
     row.put("action_use_criterion",String.valueOf(action.bdt()));
     row.put("action_eligible",action.aQ(item));row.put("full_eligible",bGl.ay(item));
     row.put("inventory_bag_found",local.dqT().x(item)!=null);
     row.put("occupation",String.valueOf(local.dtg()));row.put("fight",String.valueOf(local.doI()));
     row.put("selected_disabled",bxY.dQA()!=null&&bxY.dQA().dsA());
    }catch(Throwable error){row.put("error",error.toString());}
    items.add(row);return true;
   });
   result.put("items",items);
  }catch(Throwable error){result.put("error",error.toString());}
  return result;
 }
 public static void agentmain(String output,Instrumentation ignored)throws Exception {
  Map<String,Object> result=new LinkedHashMap<>();
  SwingUtilities.invokeAndWait(()->result.putAll(diagnostic()));
  Files.writeString(Path.of(output),new Gson().toJson(result)+"\n");
 }
}

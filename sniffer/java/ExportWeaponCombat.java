import java.nio.file.*;
import java.util.*;
import com.google.gson.Gson;

/** Offline installed slot15 attacks and full native effect trees. */
public class ExportWeaponCombat {
 static void atomicWrite(Path destination,String value) throws Exception {
  Path temporary=Files.createTempFile(destination.toAbsolutePath().getParent(),"weapon-export-",".tmp");
  try {Files.writeString(temporary,value);Files.move(temporary,destination,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);}
  finally {Files.deleteIfExists(temporary);}
 }
 public static void main(String[] args) throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX g){ExportSpellEffectTrees.groups.put(g.d(),g.cku());}});
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw e){ExportSpellEffectTrees.expressions.put(e.aZE(),e.cyi());}});
  List<Object> items=new ArrayList<>();
  apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO raw){
   bJp item=new bIJ().f(raw);
   if(item.dLn()==null || !item.dLn().v(fnO.gf((byte)15)))return;
   Map<String,Object> record=new LinkedHashMap<>();
   record.put("reference",item.d());record.put("item_level",item.cmZ());
   record.put("native_bfi",item.bfi());record.put("native_gjf",item.gjf());
   record.put("native_gji",item.gji());record.put("native_gjh",item.gjh());
   record.put("ap_cost",item.gjf());record.put("mp_cost",item.gji());record.put("wp_cost",item.gjh());
   record.put("native_cpF",item.cpF());record.put("native_cpG",item.cpG());
   record.put("native_gjk",item.gjk());record.put("native_gjj",item.gjj());
   record.put("native_gjl",item.gjl());record.put("native_gjn",item.gjn());
   amb criterion=item.a(fnE.sGE);record.put("native_use_criteria",criterion==null?"":criterion.toString());
   fnR instance=fnR.k(item);
   record.put("container_type",instance.aZY());record.put("container_reference",instance.QF());
   List<Object> roots=new ArrayList<>();
   item.gjg().forEachRemaining(e->{
    if(e.aZD()!=0 || e.fKP()){
     roots.add(Map.of("reference",e.aZE(),"execution_mode",e.aZD(),"variant",e.aZR(),"active",e.fKP()));
     ExportSpellEffectTrees.effect(e.aZE());
    }
   });
   record.put("roots",roots);items.add(record);
  }});
  atomicWrite(Path.of(args[0]),new Gson().toJson(Map.of("source","Installed bIJ/fpC/fnR; raw native properties retained until callers establish semantics","items",items))+"\n");
  atomicWrite(Path.of(args[1]),String.join("\n",ExportSpellEffectTrees.effects)+"\n");
  System.out.println("Exported "+items.size()+" slot15 templates and "+ExportSpellEffectTrees.effects.size()+" effect definitions");
 }
}

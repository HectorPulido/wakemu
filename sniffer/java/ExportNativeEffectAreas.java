import java.nio.file.*;import java.util.*;import com.google.gson.GsonBuilder;
/** Installed aKa -> bcN/Qr/faV definitions only; no graphics or network. */
public class ExportNativeEffectAreas {
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Map<String,Object> rows=new TreeMap<>();
  apw.bGL().a(new aKa(),new apB<aKa>(){public void load(aKa a){
   Map<String,Object> r=new LinkedHashMap<>();
   r.put("reference",a.d());r.put("type",a.aMO());r.put("maximum_level",a.Fq());
   r.put("shape_id",a.ckx());r.put("shape_parameters",a.ckA());
   r.put("effect_ids",a.cku());r.put("properties",a.ckD());r.put("characteristics",a.ckE());
   r.put("native_removal_masks",a.ckD());r.put("native_fight_properties",a.ckD());r.put("native_area_properties",a.ckE());
   r.put("entry_masks",a.ckB());r.put("exit_masks",a.ckC());
   r.put("raw_bde",a.bde());r.put("raw_bdf",a.bdf());r.put("raw_bdg",a.bdg());r.put("raw_bdh",a.bdh());
   r.put("raw_bcR",a.bcR());r.put("raw_bdi",a.bdi());r.put("raw_ckz",a.ckz());r.put("raw_bcS",a.bcS());
   r.put("visual",List.of(a.ckF()==null?"":a.ckF(),a.ckG()==null?"":a.ckG(),a.ckH()==null?"":a.ckH(),a.ckI()==null?"":a.ckI()));
   faV area=bcN.hFx.a(a);r.put("native_class",area==null?null:area.getClass().getSimpleName());
   if(area!=null){r.put("native_shape_class",area.bcD().getClass().getSimpleName());r.put("native_shape_description",area.bcD().bEm());r.put("native_type_id",area.aeV());r.put("native_hour_contract",area instanceof faZ);r.put("native_container_type",area.aZY());
    if(area.bcD() instanceof anE || area.bcD() instanceof anJ){
     List<List<Integer>> points=new ArrayList<>();for(int[] point:area.bcD().bEl())points.add(List.of(point[0],point[1]));r.put("native_area_points",points);
    }
   }
   rows.put(""+a.d(),r);
  }});
  Path output=Path.of(args[0]),temporary=output.resolveSibling(output.getFileName()+".tmp");
  Files.writeString(temporary,new GsonBuilder().setPrettyPrinting().create().toJson(Map.of(
    "source","Installed aKa -> bcN -> Qr/faV, offline; raw fields retained without invented semantics", "areas",rows,
    "fields_evidence",Map.of("native_removal_masks","aKa.ckD -> bcN.a -> faV.rLR; faV.a(BitSet,Qe,amP) -> Qf.q/Qs.b after Qq callbacks",
      "native_fight_properties","Historical mislabeled alias of ckD removal masks; not actor properties",
      "native_area_properties","aKa.ckE -> bcN.a -> faV.M(int[]) -> fbo.Tn",
      "characteristics","Historical alias of ckE, actually area properties; retained for compatibility",
      "running_effect_manager","faV.bax creates eZV iff fbo.GENERATE_RUNNING_EFFECT_MANAGER id12")))+"\n");
  Files.move(temporary,output,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
  System.out.println("Exported "+rows.size()+" native effect areas");
 }
}

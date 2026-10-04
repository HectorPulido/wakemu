import java.nio.file.Path;
import java.util.*;
public class ExportHealingItems{
 public static void main(String[]args)throws Exception{
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
 System.out.print("{\"source\":\"Installed bIJ/fpC item effects; neutral healing generic25 eVi/eXs\",\"items\":[");
 boolean[]first={true};apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO raw){try{
 bJp item=new bIJ().f(raw);List<eVn>effects=new ArrayList<>();item.gjg().forEachRemaining(effects::add);
 if(effects.stream().noneMatch(e->e.awM()==25))return;
 if(!first[0])System.out.print(",");first[0]=false;
 System.out.print("{\"reference\":"+item.d()+",\"item_level\":"+item.cmZ()+",\"gfx_id\":"+item.bwX()+",\"use_action\":"+(item.gfJ()!=null)+",\"use_criteria\":"+(item.a(fnE.sGH)!=null)+",\"effects\":[");
 boolean f=true;for(eVn e:effects){if(!f)System.out.print(",");f=false;
 System.out.print("{\"id\":"+e.aZE()+",\"parameter_count\":"+e.fKJ()+",\"generic\":"+e.awM()+",\"params\":"+Arrays.toString(e.fKI())+",\"target_mask\":"+e.aZR()+",\"effect_criteria\":"+(e.fKT()!=null)+",\"value_at_item_level\":"+(e.fKI().length==0?0:e.a(0,item.cmZ(),eVh.rpA))+"}");}
 System.out.print("]}");
 }catch(Throwable t){System.err.println("Skipping "+raw.d()+" "+t);}}});System.out.println("]}");
 }
}

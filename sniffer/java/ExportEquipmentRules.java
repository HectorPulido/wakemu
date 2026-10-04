import java.nio.file.Path;
/** Installed native item equipment slots; does not grant or equip any item. */
public class ExportEquipmentRules {
 public static void main(String[]args)throws Exception{
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
 System.out.print("{\"source\":\"Native bIJ/fpY slots and occupations; nonempty conditions require native evaluation\",\"items\":[");
 final boolean[] first={true};
 apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO raw){try{
 bJp item=new bIJ().f(raw); if(item.dLn()==null)return;
 var slots=new java.util.ArrayList<Integer>();for(fnO slot:fnO.values())if(item.dLn().v(slot))slots.add((int)slot.aKg());
 if(slots.isEmpty())return;
 var occupied=new java.util.ArrayList<Integer>();if(item.dLn().gkp()!=null)for(fnO slot:item.dLn().gkp())occupied.add((int)slot.aKg());
 boolean conditions=item.gjd().hasNext();
 if(!first[0])System.out.print(",");first[0]=false;
 System.out.print("{\"reference\":"+item.d()+",\"native_dte\":"+item.dte()+",\"minimum_level\":"+item.cmZ()+",\"slots\":"+slots+",\"occupied_slots\":"+occupied+",\"has_conditions\":"+conditions+"}");
 }catch(Throwable failure){System.err.println("Skipped item "+raw.d()+": "+failure.getClass().getSimpleName());}}});
 System.out.println("]}");
 }
}

import java.nio.file.Path;
import java.util.*;
/** Offline native equipment effects; no ownership or accounts are modified. */
public class ExportEquipmentEffects {
 public static void main(String[]args)throws Exception{
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
 System.out.print("{\"source\":\"Installed bIJ/fpC effects, evaluated at item level by eVn.a\",\"items\":[");
 boolean[]first={true};apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO raw){try{
 bJp item=new bIJ().f(raw);if(item.dLn()==null)return;
 var effects=new ArrayList<eVn>();item.gjg().forEachRemaining(effects::add);if(effects.isEmpty())return;
 if(!first[0])System.out.print(",");first[0]=false;
 System.out.print("{\"reference\":"+item.d()+",\"item_level\":"+item.cmZ()+",\"effects\":[");
 boolean f=true;for(eVn e:effects){if(!f)System.out.print(",");f=false;Object runner=eVi.fLJ().pS(e.awM()); PC stat=null;if(runner instanceof eWN n)stat=n.fNI();else if(runner instanceof eWW n)stat=n.fNI();
 System.out.print("{\"id\":"+e.aZE()+",\"generic\":"+e.awM()+",\"runner\":\""+(runner==null?"":runner.getClass().getName())+"\",\"params\":"+Arrays.toString(e.fKI())+",\"stat_id\":"+(stat==null?-1:(stat.aKg()&255))+",\"stat_limit\":"+(stat==null?-1:stat.aZt())+",\"stat_name\":\""+(stat==null?"":stat.toString())+"\",\"has_triggers\":"+(e.fKV().hasNext()||e.fKW().hasNext())+",\"parameter_count\":"+e.fKJ()+",\"native_variant\":"+e.aZD()+",\"native_active_effect\":"+e.fKP()+",\"target_mask\":"+e.aZR()+",\"effect_criteria\":"+(e.fKT()!=null)+",\"values\":[");
 for(int n=0;n<e.fKI().length/2;n++){if(n>0)System.out.print(",");System.out.print(e.a(n,item.cmZ(),eVh.rpA));}System.out.print("]}");}
 System.out.print("]}");
 }catch(Throwable t){System.err.println("Skipping "+raw.d()+" "+t);}}});System.out.println("]}");
 }
}

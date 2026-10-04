import java.nio.file.Path;
public class ExportBagRules {
 public static void main(String[]args)throws Exception{
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
 System.out.print("{\"source\":\"aKl via bbe to fnJ:clz capacity,clB accepted item types\",\"bags\":[");
 final java.util.Map<Integer,bJp> items=new java.util.HashMap<>();
 apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO raw){items.put(raw.d(),new bIJ().f(raw));}});
 final boolean[]first={true};
 apw.bGL().a(new aKl(),new apB<aKl>(){public void load(aKl raw){
 bJp item=items.get(raw.d());if(item==null)throw new IllegalStateException("Missing native bag item "+raw.d());
 if(!first[0])System.out.print(",");first[0]=false;
 System.out.print("{\"reference\":"+raw.d()+",\"capacity\":"+raw.clz()+",\"accepted_types\":"+java.util.Arrays.toString(raw.clB())+",\"minimum_level\":"+item.cmZ()+",\"has_equip_criteria\":"+(item.a(fnE.sGF)!=null)+"}");}});
 System.out.println("]}");
 }
}

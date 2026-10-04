import java.nio.file.Path;
/** Native item action and deletion criteria; no account/client connection. */
public class ExportInventoryActions {
 public static void main(String[]args)throws Exception {
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
 System.out.print("{\"source\":\"bIJ installed aLO; dcu destruction fnE.sGG/sGK; use fpC.gfJ\",\"items\":[");
 final boolean[] first={true};
 apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO raw){try{
 bJp item=new bIJ().f(raw);foH action=item.gfJ();
 if(!first[0])System.out.print(",");first[0]=false;
 System.out.print("{\"reference\":"+item.d()+",\"destroy_has_criteria\":"+(item.a(fnE.sGG)!=null||item.a(fnE.sGK)!=null)+",\"use_action_id\":"+(action==null?"null":action.d())+",\"use_action_class\":"+(action==null?"null":"\""+action.getClass().getName()+"\"")+",\"use_has_criteria\":"+(item.a(fnE.sGH)!=null)+"}");
 }catch(Throwable failure){System.err.println("Skipped "+raw.d());}}});
 System.out.println("]}");
 }
}

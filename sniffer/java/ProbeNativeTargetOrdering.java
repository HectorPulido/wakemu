import java.util.*;import java.lang.reflect.*;import java.nio.file.*;import com.google.gson.GsonBuilder;
/** Native faH private sort/cap, including target-cell anchor, stable ties/priority. */
public class ProbeNativeTargetOrdering {
 static PV actor(long id,int x,int y){return(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->switch(m.getName()){
  case "Sn"->id;case "baM"->new aBn(x,y,(short)0);default->throw new UnsupportedOperationException(m.getName());});}
 public static void main(String[]args)throws Exception{
  List<Map<String,Object>> rows=new ArrayList<>();
  Method sort=faH.class.getDeclaredMethod("a",List.class,eVn.class,int.class,int.class);sort.setAccessible(true);
  Method limit=faH.class.getDeclaredMethod("a",List.class,byte.class);limit.setAccessible(true);
  for(int[] flags:new int[][]{{14},{26},{14,26}})for(byte maximum:new byte[]{-1,0,1,3}){
   eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->{
    if(m.getName().equals("a")){for(int flag:flags)if(a[0]==eVl.SM(flag))return true;return false;}
    throw new UnsupportedOperationException(m.getName());});
   List<PV> actors=new ArrayList<>(List.of(actor(7,0,0),actor(2,3,1),actor(9,3,-1),actor(5,2,0)));
   sort.invoke(new faH(),actors,definition,2,0);
   List<PV> selected=(List<PV>)limit.invoke(new faH(),actors,maximum);
   rows.add(Map.of("flags",flags,"maximum_targets",(int)maximum,"cell",List.of(2,0),
                   "actors",List.of(List.of(7,0,0),List.of(2,3,1),List.of(9,3,-1),List.of(5,2,0)),
                   "ordered",selected.stream().map(PV::Sn).toList()));
  }
  Files.writeString(Path.of(args[0]),new GsonBuilder().create().toJson(rows)+"\n");
  System.out.println("Native faH distance target ordering/cap "+rows.size()+" cases PASS");
 }
}

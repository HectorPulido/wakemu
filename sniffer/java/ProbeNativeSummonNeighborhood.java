import java.util.*;
import java.nio.file.*;
import org.antlr.runtime.*;
import com.google.gson.GsonBuilder;
/** Original eMP parser signatures and aBn cH/cI neighborhood geometry. */
public class ProbeNativeSummonNeighborhood {
 public static void main(String[] args)throws Exception {
  for(String expression:new String[]{"HasSurroundingCellWithOwnSummon(\"target\",3794)","HasSurroundingCellWithOwnSummon(\"target\",\"MOORE\")","HasSurroundingCellWithOwnSummon(\"target\",3794,\"VON_NEUMANN\")"}){
   eQd parser=new eQd(new CommonTokenStream(new eQb(new ANTLRStringStream(expression))));
   ArrayList<alS> list=parser.fGv();
   if(parser.getNumberOfSyntaxErrors()!=0 || !(list.get(list.size()-1) instanceof eMP))throw new AssertionError(expression);
  }
  List<Map<String,Object>> rows=new ArrayList<>();
  for(int center:new int[]{0,Integer.MIN_VALUE,Integer.MAX_VALUE})for(int dx=-2;dx<=2;dx++)for(int dy=-2;dy<=2;dy++){
   aBn point=new aBn(center,center);int x=center+dx,y=center+dy;
   rows.add(Map.of("center",center,"x",x,"y",y,"MOORE",point.cI(x,y),"VON_NEUMANN",point.cH(x,y)));
  }
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("rows",rows)));
  System.out.println("PASS original eMP parser + cH/cI rows="+rows.size());
 }
}

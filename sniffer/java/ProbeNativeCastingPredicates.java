import java.util.*;
import java.nio.file.*;
import org.antlr.runtime.*;
import com.google.gson.GsonBuilder;
/** Original parser identities and aBn.y direction oracle for eNR. */
public class ProbeNativeCastingPredicates {
 public static void main(String[] args) throws Exception {
  Map<String,Object> out = new LinkedHashMap<>();
  Map<String,String> identities = new LinkedHashMap<>();
  for (String expression : new String[]{"IsFreeCell(\"target\",1,0)", "IsOwnArea()", "IsOwnArea(true)", "NbGates(\"caster\",\"forOwner\")"}) {
   eQd parser = new eQd(new CommonTokenStream(new eQb(new ANTLRStringStream(expression))));
   ArrayList<alS> parsed = parser.fGv();
   if (parser.getNumberOfSyntaxErrors()!=0) throw new AssertionError(expression);
   identities.put(expression, parsed.get(parsed.size()-1).getClass().getName());
  }
  List<Map<String,Object>> rows = new ArrayList<>();
  for (int x=-8;x<=8;x++) for(int y=-8;y<=8;y++) {
   aAS direction = new aBn(0,0).y(new aBn(x,y));
   Map<String,Object> row=new LinkedHashMap<>(); row.put("x",x);row.put("y",y);
   row.put("vector",direction==null?null:new int[]{direction.dyJ,direction.dyK});rows.add(row);
  }
  out.put("parser_classes",identities);out.put("direction_rows",rows);
  Files.writeString(Path.of(args[0]),new GsonBuilder().serializeNulls().setPrettyPrinting().create().toJson(out));
  System.out.println("Original parser signatures="+identities+" direction rows="+rows.size());
 }
}

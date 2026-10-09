import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;
/** Original final eYi.C and eYi.j; no data catalog or network. */
public class ProbeNativeDistanceLevelGroup1080 {
 static void set(Object object,String name,Object value)throws Exception {
  for(Class<?> type=object.getClass();type!=null;type=type.getSuperclass()){
   try{Field f=type.getDeclaredField(name);f.setAccessible(true);f.set(object,value);return;}
   catch(NoSuchFieldException missing){}
  }throw new NoSuchFieldException(name);
 }
 public static void main(String[]args)throws Exception {
  List<Map<String,Object>> rows=new ArrayList<>();
  int[][] cells={{0,0,0,3,4,0},{3,4,-100,3,4,100},{-4,8,100,8,-4,-100},
   {0,0,0,Integer.MIN_VALUE,0,0},{Integer.MAX_VALUE,0,0,Integer.MIN_VALUE,0,0},
   {0,0,0,Integer.MAX_VALUE,Integer.MAX_VALUE,0}};
  Method child=eYi.class.getDeclaredMethod("j",eZR.class);child.setAccessible(true);
  int assertions=0;
  for(int[]cell:cells)for(float factor:new float[]{0,.5f,1,-.5f,1.25f,Float.NaN,Float.POSITIVE_INFINITY,Float.NEGATIVE_INFINITY}){
   eYi runner=new eYi();aBn source=new aBn(cell[0],cell[1],(short)cell[2]);
   PV caster=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->{
    if(m.getName().equals("baM"))return source;
    throw new UnsupportedOperationException(m.getName());});
   eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->{
    if(m.getName().equals("w"))return factor;
    throw new UnsupportedOperationException(m.getName());});
   set(runner,"bfp",definition);set(runner,"bfr",caster);set(runner,"bft",new aBn(cell[3],cell[4],(short)cell[5]));
   runner.C(null);eVt context=(eVt)child.invoke(runner,new Object[]{null});
   if(context.Oh()!=runner.getValue()||context.fLN()||context.fLO())throw new AssertionError("eYi context");
   if(runner.bbA()||!runner.bbB()||!runner.bbz())throw new AssertionError("eWd targeting");
   assertions+=2;
   Map<String,Object> row=new LinkedHashMap<>();row.put("source",List.of(cell[0],cell[1],cell[2]));
   row.put("target",List.of(cell[3],cell[4],cell[5]));row.put("factor",Float.toString(factor));row.put("amount",runner.getValue());
   rows.add(row);context.bal();
  }
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("rows",rows,"native_assertions",assertions))+"\n");
  System.out.println("PASS original eYi1080: "+rows.size()+" C/SP cases, "+assertions+" assertions");
 }
}

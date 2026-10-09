import java.io.*;
import java.lang.reflect.*;
import java.util.*;

/** Original eNX/eNY conditions. stdin CSV x1,y1,x2,y2; no catalogs/services. */
public class ProbeNativeAlignmentPredicates {
 public static void main(String[] args) throws Exception {
  Field field=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");field.setAccessible(true);
  sun.misc.Unsafe unsafe=(sun.misc.Unsafe)field.get(null);
  ProbeNativeActiveSpell.Fight fight=(ProbeNativeActiveSpell.Fight)unsafe.allocateInstance(ProbeNativeActiveSpell.Fight.class);
  eNX aligned=new eNX(new ArrayList<alS>());eNY diagonal=new eNY(new ArrayList<alS>());
  if(diagonal.a(null,null,null,fight)!=-1||diagonal.a(new aBn(0,0,(short)0),null,null,fight)!=-1||diagonal.a(new aBn(0,0,(short)0),new aBn(0,0,(short)0),null,null)!=-1)throw new AssertionError("native null prerequisites");
  BufferedReader input=new BufferedReader(new InputStreamReader(System.in));String line;int count=0;
  while((line=input.readLine())!=null){String[] v=line.split(",");if(v.length!=4)throw new IllegalArgumentException(line);
   aBn a=new aBn(Integer.parseInt(v[0]),Integer.parseInt(v[1]),(short)0),b=new aBn(Integer.parseInt(v[2]),Integer.parseInt(v[3]),(short)7);
   System.out.println(aligned.a(a,b,null,fight)+","+diagonal.a(a,b,null,fight));count++;
  }
  System.err.println("Original eNX/eNY rows="+count+"; null prerequisite assertions pass");
 }
}

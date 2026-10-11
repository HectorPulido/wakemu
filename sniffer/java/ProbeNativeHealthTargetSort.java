import java.util.*;
import java.lang.reflect.*;
/** Actual faH/faK health sort and signed target cap with native presence. */
public class ProbeNativeHealthTargetSort {
 public static void main(String[] args) throws Exception {
  Method sort=faH.class.getDeclaredMethod("a",List.class,eVn.class,int.class,int.class);
  Method limit=faH.class.getDeclaredMethod("a",List.class,byte.class);
  sort.setAccessible(true); limit.setAccessible(true);
  int[][] operands={{50,100},{10,100},{20,200},{0,0},{1,0},{0,1}};
  for(int mode=0;mode<3;mode++) for(int rotation=0;rotation<8;rotation++) for(byte maximum:new byte[]{0,2,4}) {
   final int flagsMode=mode;
   eVn effect=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->{
    if(m.getName().equals("a"))return a[0]==eVl.rwE || flagsMode==1&&a[0]==eVl.rwW || flagsMode==2&&a[0]==eVl.rwV;
    throw new UnsupportedOperationException(m.getName());
   });
   List<PV> targets=new ArrayList<>(); IdentityHashMap<PV,Integer> ids=new IdentityHashMap<>();
   for(int j=0;j<8;j++) {
    int i=(j+rotation)%8; int[] hp=i>=6?new int[]{0,0}:operands[i];
    PV pv=ProbeNativeHealthTargetOrdering.actor(i<6,hp[0],hp[1]);targets.add(pv);ids.put(pv,i);
   }
   sort.invoke(new faH(),targets,effect,0,0);
   List<PV> result=(List<PV>)limit.invoke(new faH(),targets,maximum);
   System.out.print(mode+"\t"+rotation+"\t"+maximum+"\t");
   System.out.println(String.join(",",result.stream().map(pv->""+ids.get(pv)).toList()));
  }
 }
}

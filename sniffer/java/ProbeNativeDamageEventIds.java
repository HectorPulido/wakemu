import java.lang.reflect.*;import java.util.*;
/** Native eXt.bbx for real eVi families with an explicit spell-container11 fixture. */
public class ProbeNativeDamageEventIds {
 static eVo container(int kind){return(eVo)Proxy.newProxyInstance(eVo.class.getClassLoader(),new Class[]{eVo.class},(p,m,a)->switch(m.getName()){
  case "aZY"->kind;case "toString"->"Container"+kind;default->throw new UnsupportedOperationException(m.getName());});}
 static eVn flags(int...flags){Set<Integer> set=new HashSet<>();for(int f:flags)set.add(f);
  return(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->switch(m.getName()){
   case "aZO"->new BitSet();case "a"->set.contains((int)((eVl)a[0]).fLK());case "toString"->"Flags"+set;default->throw new UnsupportedOperationException(m.getName());});}
 static BitSet events(int kind,int container,int...flags){eXt damage=(eXt)eVi.fLJ().pS(kind);damage.a(container(container));damage.b(flags(flags));damage.bbx();return damage.bbw();}
 public static void main(String[]args){
  for(int kind=1;kind<=5;kind++)System.out.println(kind+" spell11="+events(kind,11)+" state3="+events(kind,3));
  System.out.println("flags4/22/23/24="+events(1,11,4,22,23,24));
  System.out.println("state3 flag34="+events(1,3,34));
 }
}

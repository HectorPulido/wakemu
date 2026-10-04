import java.util.*;
import com.google.gson.Gson;
public class ProbeNativeFacing {
 public static void main(String[] args){
  Map<Integer,Object> dirs=new TreeMap<>();
  for(int n=0;n<8;n++){aAS d=aAS.wL(n);Sl s=new Sl();s.a(0,0,(short)0,d);
   dirs.put(n,Map.of("direction",d.toString(),"vector",List.of(d.dyJ,d.dyK),"at_1_0",s.o(1,0,(short)0).toString(),"at_0_1",s.o(0,1,(short)0).toString()));}
  System.out.println(new Gson().toJson(dirs));
 }
}

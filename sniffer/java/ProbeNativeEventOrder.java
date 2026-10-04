import java.util.*;
import gnu.trove.map.hash.TLongObjectHashMap;
public class ProbeNativeEventOrder {
 static class Effect extends eYg {
  final int priority,generic;
  Effect(long uid,int priority,int generic){this.bfx=uid;this.priority=priority;this.generic=generic;}
  public int aZM(){return priority;}
  public int aZE(){return generic;}
 }
 public static void main(String[]args){
  TLongObjectHashMap<Qe> map=new TLongObjectHashMap<>();
  for(Effect e:List.of(new Effect(901,0,9),new Effect(904,5,12),new Effect(903,5,10),new Effect(902,5,10)))map.put(e.LV(),e);
  List<Long> uids=new ArrayList<>(List.of(901L,904L,903L,902L));uids.sort(new eZY(map));
  if(!uids.equals(List.of(902L,903L,904L,901L)))throw new AssertionError(uids);
  System.out.println(uids);
 }
}

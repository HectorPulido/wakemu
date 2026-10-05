import java.lang.reflect.*;
import java.util.*;
/** Original ePj/eOv/eOG constructor contracts and known-null evaluation. */
public class ProbeNativeReadyAreaConditions {
 static Object field(Object object,String name)throws Exception{
  for(Class<?> type=object.getClass();type!=null;type=type.getSuperclass()){
   try{Field f=type.getDeclaredField(name);f.setAccessible(true);return f.get(object);}
   catch(NoSuchFieldException missing){}
  }
  throw new NoSuchFieldException(name);
 }
 static ArrayList<alS> params(alS...values){return new ArrayList<>(Arrays.asList(values));}
 public static void main(String[]args)throws Exception{
  ePj all=new ePj(params(new alw(4294968842L)));
  ePj owned=new ePj(params(new alw(1546),new amc("triggeringTarget")));
  if(!field(all,"qfe").equals(true)||!field(all,"mzr").equals(4294968842L))throw new AssertionError("global long base identity");
  if(!field(owned,"qfe").equals(false)||!field(owned,"pVO").equals("triggeringTarget"))throw new AssertionError("selected owner");
  Object caster=ProbeNativeEffectUIDs.actor(7);
  for(alS filter:new alS[]{new alu(true),new alu(false),new amc("ownAreas"),new amc("teamAreas"),new amc("other")}){
   eOv criterion=new eOv(params(new amc("triggeringTarget"),new alw(1546),filter));
   byte expected=filter instanceof amb?(((amb)filter).b(null,null,null,null)?(byte)2:(byte)1):
    ((amc)filter).getValue().equals("ownAreas")?(byte)2:((amc)filter).getValue().equals("teamAreas")?(byte)3:(byte)1;
   if(!field(criterion,"qej").equals(expected)||criterion.a(caster,null,null,null)!=-1)throw new AssertionError("filter/null actor");
  }
  Field unsafeField=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");unsafeField.setAccessible(true);
  Object fighter=((sun.misc.Unsafe)unsafeField.get(null)).allocateInstance(ProbeNativeOwnSummon.Actor.class);
  eOG summon=new eOG(params(new amc("triggeringTarget")));
  if(!field(summon,"pVO").equals("triggeringTarget")||summon.a(fighter,null,null,null)!=-1)throw new AssertionError("known-null own summon");
  System.out.println("PASS original NbAreasWithBaseId long/all/selectedowner +5 specific-area filters + triggeringTarget known-null eOv/eOG");
 }
}

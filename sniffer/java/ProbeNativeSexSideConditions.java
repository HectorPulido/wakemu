import java.lang.reflect.*;
import java.util.*;
/** Original eOO/eOP evaluators, including noncanonical strings and null PV. */
public class ProbeNativeSexSideConditions {
 static class SexActor extends ProbeNativeLevelGroup.Actor {
  byte sex;
  public byte aXz(){return sex;}
 }
 static SexActor actor(byte sex)throws Exception {
  Field f=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);
  SexActor a=(SexActor)((sun.misc.Unsafe)f.get(null)).allocateInstance(SexActor.class);a.sex=sex;return a;
 }
 static eOO sex(String label,String selector){
  ArrayList<alS> a=new ArrayList<>();a.add(new amc(label));if(selector!=null)a.add(new amc(selector));return new eOO(a);
 }
 static eOP side(String selector){
  ArrayList<alS>a=new ArrayList<>();if(selector!=null)a.add(new amc(selector));return new eOP(a);
 }
 public static void main(String[]args)throws Exception {
  int assertions=0;
  for(byte actual:new byte[]{0,1,-1})for(String label:new String[]{"Male","mAlE","Female","other",""})
   for(String selector:new String[]{null,"target","TARGET","other"}){
    SexActor caster=actor(actual),target=actor((byte)(actual==0?1:0));
    boolean select=selector!=null&&selector.equalsIgnoreCase("target");
    byte chosen=select?target.sex:caster.sex;int expected=chosen==(label.equalsIgnoreCase("Male")?0:1)?0:1;
    if(sex(label,selector).a(caster,target,null,null)!=expected)throw new AssertionError("eOO string/sex");assertions++;
   }
  if(sex("Male","target").a(actor((byte)0),null,null,null)!=-1)throw new AssertionError("eOO null");assertions++;
  for(int[] point:new int[][]{{0,1},{0,-1},{1,0},{-1,0}}){
   ProbeNativeBackstabbed.Actor caster=ProbeNativeBackstabbed.actor(0,0,0,1);
   ProbeNativeBackstabbed.Actor target=ProbeNativeBackstabbed.actor(point[0],point[1],0,1);
   int expected=point[0]==0?0:-1;
   for(String selector:new String[]{null,"target","other"}){
    int actual=side(selector).a(caster,target,null,null);
    if(actual!=expected)throw new AssertionError("eOP lateral "+Arrays.toString(point)+" selector="+selector+" actual="+actual+" expected="+expected);assertions++;
   }
   target.locator=null;
   if(side("target").a(caster,target,null,null)!=-1)throw new AssertionError("eOP locator");assertions++;
  }
  System.out.println("PASS original eOO/eOP: "+assertions+" assertions");
 }
}

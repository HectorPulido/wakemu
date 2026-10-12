import java.lang.reflect.*;
import java.util.*;
/** Installed eNz criterion with actual QI registration and actual eGj objects. */
public final class ProbeNativeCasterFacingFighter {
 static class Actor extends ProbeNativeLevelGroup.Actor {
  int x,y;short z;byte radius,slot=-1;aAS direction;
  public aBn baM(){return new aBn(x,y,z);}public aAS bcy(){return direction;}
  public int bcz(){return x;}public int bcA(){return y;}public short bcB(){return z;}
  public byte bcL(){return radius;}public byte bcK(){return radius;}
  public boolean bcO(){return true;}public boolean bcP(){return false;}public boolean bcQ(){return false;}
  public void M(byte n){slot=n;}public byte bcN(){return slot;}
 }
 static void check(eNz condition,Actor caster,Object target,Object fight,int expected,String label){
  int result=condition.a(caster,target,null,fight);
  if(result!=expected)throw new AssertionError(label+":"+result+" != "+expected);
  System.out.println("PASS "+label+"="+result);
 }
 public static void main(String[] args)throws Exception {
  Field field=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");field.setAccessible(true);
  sun.misc.Unsafe u=(sun.misc.Unsafe)field.get(null);
  Actor caster=(Actor)u.allocateInstance(Actor.class);caster.x=1;caster.y=1;caster.slot=-1;
  for(aAS d:aAS.values())if(d.dyI==1)caster.direction=d;
  ProbeNativeFightersBreedRange.F fight=(ProbeNativeFightersBreedRange.F)u.allocateInstance(ProbeNativeFightersBreedRange.F.class);
  ProbeNativeQIRegistry.Grid grid=new ProbeNativeQIRegistry.Grid();
  Field qi=fcb.class.getDeclaredField("rRQ");qi.setAccessible(true);qi.set(fight,grid);
  grid.f(caster);
  eNz condition=new eNz(new ArrayList<alS>());
  check(condition,caster,null,fight,-1,"emptyAhead");
  Actor target=(Actor)u.allocateInstance(Actor.class);target.x=3;target.y=1;target.z=19;target.radius=1;target.slot=-1;
  grid.f(target);
  check(condition,caster,null,fight,0,"footprintAcrossZWithoutSelectedTarget");
  grid.g(target);
  check(condition,caster,target,fight,-1,"selectedTargetDoesNotSubstituteOccupancy");
  grid.g(caster);caster.radius=1;grid.f(caster);
  check(condition,caster,null,fight,0,"casterOwnFootprint");
 }
}

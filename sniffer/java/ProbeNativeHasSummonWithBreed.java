import java.util.*;
/** Invoke original eMI; only fUQ/dpu identity facts are supplied by the fixture. */
public class ProbeNativeHasSummonWithBreed {
 static class A extends ProbeNativeFightersBreedRange.A {
  long id; eGj master;
  public long Sn(){return id;}
  public eGj dpu(){return master==null?this:master;}
 }
 static A actor(long id,int breed,eGj master)throws Exception {
  A a=(A)ProbeNativeFightersBreedRange.U.allocateInstance(A.class);
  a.id=id;a.breed=(short)breed;a.master=master;return a;
 }
 static int query(Object caster,ProbeNativeFightersBreedRange.F f,long breed){
  return new eMI(new ArrayList<alS>(List.of(new alw(breed)))).a(caster,null,null,f);
 }
 static void check(int actual,int expected,String label){
  if(actual!=expected)throw new AssertionError(label+":"+actual+"/"+expected);
  System.out.println("PASS "+label+"="+actual);
 }
 public static void main(String[]args)throws Exception {
  A own=actor(7,7,null),other=actor(8,7,null),child=actor(9,81,own),grandchild=actor(10,82,child);
  ProbeNativeFightersBreedRange.F f=(ProbeNativeFightersBreedRange.F)ProbeNativeFightersBreedRange.U.allocateInstance(ProbeNativeFightersBreedRange.F.class);
  f.roster=List.of(own,other);check(query(own,f,7),-1,"selfAndOrdinaryDoNotCount");
  f.roster=List.of(own,child,grandchild);check(query(own,f,81),0,"directOwner");
  check(query(own,f,82),-1,"notRecursiveRoot");check(query(child,f,82),0,"nestedDirectOwner");
  child.hp=0;child.excluded=true;check(query(own,f,81),0,"KOAndSemNotFiltered");
  check(query(own,f,65536+81),-1,"requestedLongNotNarrowed");
  check(query(new Object(),f,81),-1,"nonAmPCaller");
  check(query(own,null,81),-1,"missingFight");
 }
}

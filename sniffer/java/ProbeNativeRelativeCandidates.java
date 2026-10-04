import java.lang.reflect.*;
import java.util.*;
public class ProbeNativeRelativeCandidates {
 static amP actor(int x,int y) {
  return (amP)Proxy.newProxyInstance(amP.class.getClassLoader(),new Class[]{amO.class,QK.class},(p,m,a)->{
   switch(m.getName()) {
    case "bEe":return true;case "bcM":return (byte)0;case "bcN":return (byte)0;case "bcL":return (byte)0;case "bcz":return x; case "bcA":return y;case "bcB":return (short)0;
    case "bcy":return aAS.dyA;case "Sn":return 7L;
    case "toString":return "Actor("+x+","+y+")";
   }
   Class<?> r=m.getReturnType();
   if(r==boolean.class)return false;if(r==int.class)return 0;
   if(r==byte.class)return (byte)0;if(r==short.class)return(short)0;
   if(r==long.class)return 0L;return null;
  });
 }
 public static void main(String[] args) {
  amP actor=actor(0,0);
  amJ<amP> provider=new amJ<amP>() {
   public Iterator<amP> bak(){return List.of(actor).iterator();}
   public List<amP> a(aBn p){return List.of(actor);}
   public List<amP> b(int x,int y,int z){return x==0 && y==0 && z==0?List.of(actor):List.of();}
  };
  boolean inside=amQ.bEf().a(actor,provider,anD.bEz(),0,0,(short)0,(amS)null).iterator().hasNext();
  boolean shiftedCell=amQ.bEf().a(actor,provider,anD.bEz(),10,10,(short)0,(amS)null).iterator().hasNext();
  boolean shiftedCaster=amQ.bEf().a(actor(10,10),provider,anD.bEz(),0,0,(short)0,(amS)null).iterator().hasNext();
  if(!inside||!shiftedCell||shiftedCaster)throw new AssertionError("inside="+inside+" shiftedCell="+shiftedCell+" shiftedCaster="+shiftedCaster);
  boolean fcInside=amQ.bEf().a(actor,provider,anD.bEz(),0,0,(short)0,fcE.j(new long[]{1})).iterator().hasNext();
  boolean fcShifted=amQ.bEf().a(actor,provider,anD.bEz(),10,10,(short)0,fcE.j(new long[]{1})).iterator().hasNext();
  if(!fcInside||fcShifted)throw new AssertionError("fcE1 inside="+fcInside+" shifted="+fcShifted);
  System.out.println("Native amQ fcE1 point is cell-centered: occupied→exclude; empty→eligible.");
  System.out.println("Native amQ point/null-selector is caster-anchored: shifting target cell preserves membership; shifting caster excludes actor.");
 }
}

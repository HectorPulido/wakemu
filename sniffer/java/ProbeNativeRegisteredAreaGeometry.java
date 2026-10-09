import java.lang.reflect.Proxy;
import java.util.*;

/** Actual Qq.bcT uses the owner coordinates as its geometry reference. */
public class ProbeNativeRegisteredAreaGeometry {
 static class Glyph extends faY {
  Glyph(Qr row){super(row);} Glyph(){super();}
  protected Qq bcs(){return new Glyph();}
  public List<amP> d(amP target){return n(target);}
  public anS bEs(){return bcD().bEs();}
  public void a(int x,int y,short z,Qe source){}
 }
 public static void main(String[] args){
  anE shape=new anE();shape.p(new int[]{1,0,0,1});
  PV owner=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},
   (p,m,a)->switch(m.getName()){
    case "Sn"->7L;case "bcz","bcA"->0;case "bcB"->(short)0;
    case "bav","bcM"->(byte)0;
    default->throw new UnsupportedOperationException(m.getName());
   });
  Glyph prototype=new Glyph(new Qr().oK(100).b(shape));
  faV area=prototype.b(new fbm(901,5,2,(short)9,null,7,owner,(short)1,aAS.wL(7)));
  area.bcT();
  Set<List<Integer>> actual=new HashSet<>();
  for(int[] cell:area.bcX())actual.add(List.of(cell[0],cell[1]));
  Set<List<Integer>> expected=Set.of(List.of(6,2),List.of(5,3));
  if(!actual.equals(expected))throw new AssertionError("owner reference "+actual);
  if(!area.d(new aBn(6,2,(short)-99))||area.d(new aBn(4,2,(short)9)))
   throw new AssertionError("actual cached Qq membership");
  System.out.println("PASS actual Qq.bcT owner reference, ordered point geometry, cached XY membership");
 }
}

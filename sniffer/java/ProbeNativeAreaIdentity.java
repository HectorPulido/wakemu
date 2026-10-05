/** Native Qq/faZ identity and point geometry: instance UID != prototype ID. */
public class ProbeNativeAreaIdentity {
 static class Hour extends faZ {
  Hour(Qr q){super(q);} Hour(){super();}
  protected Qq bcs(){return new Hour();}
  public java.util.List<amP> d(amP p){return n(p);}
  public anS bEs(){return bcD().bEs();}
 }
 public static void main(String[]args){
  Hour prototype=new Hour(new Qr().oK(1546).b(anD.bEz()).oN(1));
  faV area=prototype.b(new fbm(901,2,-3,(short)4,null,7,null,(short)1,aAS.wL(3)));
  area.bcT();
  if(area.Sn()!=901||area.QF()!=901||area.bct()!=1546||area.aeV()!=1)throw new AssertionError("native identities");
  if(!area.d(new aBn(2,-3,(short)99))||area.d(new aBn(2,-2,(short)4)))throw new AssertionError("native XY geometry");
  System.out.println("PASS native Qq UID901/prototype1546/type1 and point containment independent of Z");
 }
}

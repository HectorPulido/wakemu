import java.lang.reflect.*;
/** Native base eGj carry/release coordinates and reciprocal relation oracle. */
public class ProbeNativeCarryRelations {
 static class Actor extends eGj {
  public PA b(PC p){return null;}
  public void a(QM q){}
  public Qf bax(){return null;}
  public boolean dnz(){return true;}
  public eGj dpu(){return this;}
  public byte bcK(){return 0;}
  public fcb dpt(){return null;}
  public boolean a(PE p){return false;}
  public long jy(long v0){return 0L;}
  public eGA dnv(){return null;}
  public java.util.Collection<? extends eGj> dnC(){return null;}
  public eGj jt(long v0){return null;}
  public foA dnK(){return null;}
  public fnw dps(){return null;}
  public long dpS(){return 0L;}
  public eHd dpT(){return null;}
  public void dpQ(){}
  public boolean dpR(){return false;}
  protected frj dnJ(){return null;}
  public void Dg(int v0){}
  public long jx(long v0){return 0L;}
  public eGj b(long v0, aBn v1, short v2, eHD v3, SQ v4, boolean v5, eHN<ffe> v6){return null;}
  protected eGH dpU(){return null;}
  protected byte dpV(){return 0;}
  public void dnO(){}
  public float dpW(){return 0F;}
  public eRL dpX(){return null;}
  public void aQc(){}
  public int doX(){return 0;}
  public int doY(){return 0;}
  public void c(int v0, java.lang.Object v1){}
  public eGj dpr(){return null;}
 }
 static Actor actor(sun.misc.Unsafe u,int x,int y,short z)throws Exception{
  Actor a=(Actor)u.allocateInstance(Actor.class);Field position=eGj.class.getDeclaredField("pGF");position.setAccessible(true);position.set(a,new aBn(x,y,z));a.bkU=aAS.values()[0];return a;
 }
 static void check(boolean result,String label){if(!result)throw new AssertionError(label);}
 public static void main(String[] args)throws Exception{
  Field f=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);sun.misc.Unsafe u=(sun.misc.Unsafe)f.get(null);
  Actor carrier=actor(u,1,1,(short)0), carried=actor(u,2,1,(short)0);
  check(carrier.a((eHH)carried),"carry");
  check(carrier.fry()==carried&&carried.frz()==carrier,"reciprocal");
  check(carried.bcz()==1&&carried.bcA()==1,"carried position");
  check(!carrier.a((eHH)carried),"cannot recarry");
  aAS initial=carried.bcy();carrier.a(aAS.values()[2]);check(carried.bcy()!=initial,"carried direction delta");
  carrier.a(aAS.dyB);check(carrier.bcy()==aAS.dyB&&carried.bcy().dyI>=0&&carried.bcy().dyI<8,"TOP carrier, planar carried rotation");
  carrier.a(3,3,(short)1);check(carried.bcz()==3&&carried.bcA()==3&&carried.bcB()==1,"carrier movement");
  check(carrier.Q(new aBn(4,2,(short)0)),"release");
  check(!carrier.frA()&&!carried.buX()&&carried.bcz()==4&&carried.bcA()==2,"release relations/position");
  for(int dx=-2;dx<=2;dx++)for(int dy=-2;dy<=2;dy++){
   Actor c=actor(u,0,0,(short)0), t=actor(u,1,0,(short)0);c.a((eHH)t);c.Q(new aBn(dx,dy,(short)0));
   System.out.println("DIRECTION "+dx+" "+dy+" "+c.bcy().dyI+" "+t.bcy().dyI);
  }
  System.out.println("PASS actual eGj carry, reciprocal identity, nested rejection, movement and release");
 }
}

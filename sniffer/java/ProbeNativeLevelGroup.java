import java.lang.reflect.*;
public class ProbeNativeLevelGroup {
static class Actor extends eGj {public eGj dpu(){return null;} public boolean dnz(){return false;} public Qf bax(){return null;} public fcb dpt(){return null;} public void a(PE a0, PG a1){return;} public void a(QM a0){return;} public PA b(PC a0){return null;} short level; public short cmZ(){return level;} public long jy(long a0){return 0;}public eGA dnv(){return null;}public java.util.Collection<? extends eGj> dnC(){return null;}public eGj jt(long a0){return null;}public foA dnK(){return null;}public fnw dps(){return null;}public long dpS(){return 0;}public eHd dpT(){return null;}public void dpQ(){return;}public boolean dpR(){return false;}protected frj dnJ(){return null;}public void Dg(int a0){return;}public long jx(long a0){return 0;}public eGj b(long a0, aBn a1, short a2, eHD a3, SQ a4, boolean a5, eHN<ffe> a6){return null;}protected eGH dpU(){return null;}protected byte dpV(){return 0;}public void dnO(){return;}public float dpW(){return 0;}public eRL dpX(){return null;}public void aQc(){return;}public int doX(){return 0;}public int doY(){return 0;}public void c(int a0, java.lang.Object a1){return;}public eGj dpr(){return null;}}
 static void set(Object obj,Class<?> owner,String name,Object value)throws Exception{Field f=owner.getDeclaredField(name);f.setAccessible(true);f.set(obj,value);}
 public static void main(String[]args)throws Exception{
  System.out.println("dispel_default_excluded_class="+eVi.rvF.d());
  Field uf=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");uf.setAccessible(true);sun.misc.Unsafe u=(sun.misc.Unsafe)uf.get(null);
  Actor actor=(Actor)u.allocateInstance(Actor.class);
  for(int[] row:new int[][]{{200,100},{101,33},{-101,33},{32767,2147483647}}){
   actor.level=(short)row[0];eYm effect=new eYm();set(effect,Qe.class,"bfr",actor);set(effect,eYm.class,"rFA",true);set(effect,eYm.class,"rFI",row[1]);
   for(float[] linear:new float[][]{{0,1},{6.25f,.75f},{0,-.1f}}){set(effect,eYm.class,"rFD",linear[0]);set(effect,eYm.class,"rFE",linear[1]);System.out.println(row[0]+","+row[1]+","+linear[0]+","+linear[1]+" -> "+effect.d(null,false).Oh());}
  }
 }
}

import java.util.*;import java.lang.reflect.*;import sun.misc.Unsafe;
/** Real eKt/eKn calls; test actors provide owned positions/breed/property facts. */
public class ProbeNativeFightersBreedRange {
 static final Unsafe U;
 static {try{Field f=Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);U=(Unsafe)f.get(null);}catch(Exception e){throw new RuntimeException(e);}}
 static class A extends big {
  A(){super();}public cVD dpw(){return null;}public eGH dsG(){return null;}public VV dpv(){return null;}public PA b(PC p){return null;}public boolean a(PC p){return false;}public int c(PC p){return 0;}public fcb dpt(){return null;}public Qf bax(){return null;}public eGj dpu(){return null;}
  public long jy(long v0){return 0L;}
  public eGA dnv(){return null;}
  public java.util.Collection<big> dnC(){return null;}
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
  public float dpW(){return 0f;}
  public eRL dpX(){return null;}
  public void aQc(){}
  public int doX(){return 0;}
  public int doY(){return 0;}
  public void c(int v0, java.lang.Object v1){}
  public eGj dpr(){return null;}
  protected bkN dnl(){return null;}
  public void dnU(){}
  public void dnV(){}
  protected java.lang.String doD(){return null;}
  protected java.lang.String doE(){return null;}
  public byte doO(){return 0;}
  short breed;int x,y;byte radius;boolean excluded;int hp;boolean summon;
  public short aXA(){return breed;}public aBn baM(){return new aBn(x,y,(short)0);}
  public int bcz(){return x;}public int bcA(){return y;}public short bcB(){return 0;}public byte bcL(){return radius;}
  public boolean a(PE p){return p==ffe.sem&&excluded;}
 }
 static class F extends buH {F(){super(0,null,null,null,null);}Collection<big> roster;public Collection<big> fUQ(){return roster;}}
 static A a(int breed,int x,int hp,boolean summon,boolean excluded)throws Exception{A a=(A)U.allocateInstance(A.class);a.breed=(short)breed;a.x=x;a.hp=hp;a.summon=summon;a.excluded=excluded;return a;}
 static long query(F f,A caster,Object target,int radius,String selector,int breed){return new eKt(new ArrayList<alS>(List.of(new alw(radius),new amc(selector),new alw(breed)))).d(caster,target,null,f);}
 static void check(long actual,long expected,String label){if(actual!=expected)throw new AssertionError(label+":"+actual+" != "+expected);System.out.println("PASS "+label+"="+actual);}
 public static void main(String[]args)throws Exception{
  A own=a(7,0,10,false,false),ko=a(7,2,0,false,false),sum=a(7,3,10,true,false),other=a(8,1,10,false,false),excluded=a(7,1,10,false,true);sum.radius=1;
  F f=(F)U.allocateInstance(F.class);f.roster=new ArrayList<>(List.of(own,ko,sum,other,excluded));
  check(query(f,own,ko,2,"caster",7),3,"own+KO+summonFootprint");
  check(query(f,own,ko,1,"caster",7),1,"positiveRadius");
  check(query(f,own,ko,0,"caster",7),3,"zeroIgnoresDistanceExcludesSem");
  check(query(f,own,ko,-1,"caster",7),3,"negativeIgnoresDistance");
  check(query(f,own,new aBn(3,0,(short)0),1,"target",7),2,"literalTargetCell");
  check(query(f,own,new aBn(3,0,(short)0),1,"TARGET",7),0,"caseSensitiveCellSpecial");
  check(query(f,own,ko,0,"invalid",7),0,"missingCenter");
  check(query(f,own,ko,0,"caster",999),0,"exactBreed");
 }
}

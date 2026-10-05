import java.lang.reflect.*;
/** Call original eYA.D and its QI.R/X gates; no emulated Java arithmetic. */
public class ProbeNativeSymmetry {
 static class Terrain extends QI {
  boolean available=true;
  @Override public boolean R(int x,int y){return available;}
  @Override public short X(int x,int y){return (short)(x-y);}
 }
 static void set(Object object,String name,Object value)throws Exception{
  for(Class<?> c=object.getClass();c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(name);f.setAccessible(true);f.set(object,value);return;}catch(NoSuchFieldException e){}
  throw new NoSuchFieldException(name);
 }
 static byte[] payload(eYg group)throws Exception{
  eVv definition=(eVv)Proxy.newProxyInstance(eVv.class.getClassLoader(),new Class[]{eVv.class},(p,m,a)->switch(m.getName()){
   case "aZD"->(byte)2;case "en","eo"->Tt.pz(0);case "aZO"->new java.util.BitSet();case "aZE"->123;case "aZV"->Qd.bfe;case "aZW"->Qb.beO;default->throw new UnsupportedOperationException(m.getName());});
  PV actor=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->switch(m.getName()){
   case "Sn"->7L;case "bcz","bcA"->0;case "bcB"->(short)0;case "baK"->false;default->throw new UnsupportedOperationException(m.getName());});
  set(group,"bfp",definition);set(group,"bfr",actor);set(group,"bfs",null);
  set(group,"bft",new aBn(2,-3,(short)4));set(group,"bfx",901L);set(group,"bfy",901L);set(group,"rEj",false);
  return group.bca().toByteArray();
 }
 public static void main(String[] args)throws Exception {
  Terrain terrain=new Terrain();
  PN world=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(p,m,a)->{
   if(m.getName().equals("bad"))return terrain;throw new UnsupportedOperationException(m.getName());});
  eYA runner=new eYA();Field f=Qe.class.getDeclaredField("bfw");f.setAccessible(true);f.set(runner,world);
  Field angle=eYA.class.getDeclaredField("rGp");angle.setAccessible(true);
  Method rotate=eYA.class.getDeclaredMethod("D",int.class,int.class,int.class,int.class);rotate.setAccessible(true);
  int[][] rows={{90,2,3,5,7,-2,6},{180,2,3,5,7,-1,-1},{270,2,3,5,7,6,0},{180,2147483647,0,-1,0,-1,0}};
  int count=0;
  for(int[]r:rows){angle.setInt(runner,r[0]);aBn result=(aBn)rotate.invoke(runner,r[1],r[2],r[3],r[4]);
   if(result.getX()!=r[5]||result.getY()!=r[6]||result.bdn()!=(short)(r[5]-r[6]))throw new AssertionError(result.toString());count++;}
  terrain.available=false;if(rotate.invoke(runner,2,3,5,7)!=null)throw new AssertionError("Missing column accepted");count++;
  eGM.a(null);byte[] inherited=payload(new eYg()),symmetry=payload(new eYA());
  if(!java.util.Arrays.equals(inherited,symmetry))throw new AssertionError("Unexpected eYA AdditionalDatas");count++;
  if(args.length>0)java.nio.file.Files.write(java.nio.file.Path.of(args[0]),symmetry);
  System.out.println("Native eYA symmetry/QI height/blocked/int32 overflow/inherited codec: "+count+"PASS");
 }
}

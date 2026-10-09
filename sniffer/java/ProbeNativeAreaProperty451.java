import java.lang.reflect.*;
/** Original eWs/fbo/faV property mutation and removal; no network or catalog. */
public class ProbeNativeAreaProperty451 {
 static class Glyph extends faY {
  boolean los; public boolean fTq(){return los;}
  public java.util.List<amP> d(amP target){return n(target);}
  protected Qq bcs(){return new Glyph();} public int aeV(){return 0;} public int df(long id){return 0;}
  public byte bav(){return 0;} public byte[] baz(){return new byte[0];} public anS bEs(){return null;}
  public void a(int x,int y,short z,Qe source){}
 }
 static void set(Object object,String name,Object value)throws Exception {
  for(Class<?> type=object.getClass();type!=null;type=type.getSuperclass()){
   try{Field f=type.getDeclaredField(name);f.setAccessible(true);f.set(object,value);return;}
   catch(NoSuchFieldException missing){}
  }
  throw new NoSuchFieldException(name);
 }
 static int assertions;
 static void check(boolean value){assertions++;if(!value)throw new AssertionError("assertion "+assertions);}
 public static void main(String[]args)throws Exception {
  for(int i=0;i<15;i++)check(fbo.Tn(i)!=null);
  check(fbo.Tn(-1)==null);check(fbo.Tn(15)==null);check(fbo.Tn(256)==null);
  Glyph area=new Glyph(); eWs first=new eWs();eWs second=new eWs();
  set(first,"bfs",area);set(first,"aSg",10);set(second,"bfs",area);set(second,"aSg",10);
  Method apply=eWs.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);
  apply.invoke(first,null,false);check(area.a(fbo.Tn(10)));check(area.b(fbo.Tn(10))==1);
  apply.invoke(second,null,false);check(area.b(fbo.Tn(10))==1);
  first.bbR();check(!area.a(fbo.Tn(10)));second.bbR();check(!area.a(fbo.Tn(10)));
  area.f(fbo.Tn(1));set(first,"aSg",1);apply.invoke(first,null,false);first.bbR();check(!area.a(fbo.Tn(1)));
  for(boolean base:new boolean[]{false,true}){
   for(boolean transparent:new boolean[]{false,true}){
    area.los=base; if(transparent)area.f(fbo.Tn(10));else area.h(fbo.Tn(10));
    check(area.bcQ()==(base&&!transparent));
   }
  }
  System.out.println("PASS original eWs451/faV set membership: "+assertions+" assertions");
 }
}

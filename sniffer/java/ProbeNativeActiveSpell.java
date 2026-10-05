import java.util.*;
import java.lang.reflect.*;
public class ProbeNativeActiveSpell {
 static final class Fight extends fbX<eGj> {
  PZ active;
  Fight(){super(1,null,null);}
  public PZ bah(){return active;}
  public PH<eVn> aZZ(){return null;}
  protected void FU(int n){} public void dLY(){} public void y(eGj a){} protected void k(QK a){}
  public void a(Qq q,amP p){} public void b(Qq q,amP p){}
  public eGj ku(long n){return null;}
  public long baj(){return 0;} protected void a(fdo a){} public fcs dLO(){return null;}
  public void a(eGj a,List<int[]> b,fcC c){} public void aE(eGj a){} public void dMe(){}
 }
 public static void main(String[]args)throws Exception{
  Field uf=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");uf.setAccessible(true);
  sun.misc.Unsafe u=(sun.misc.Unsafe)uf.get(null);Fight f=(Fight)u.allocateInstance(Fight.class);
  eJn criterion=new eJn(new ArrayList<alS>());
  if(criterion.d(null,null,null,null)!=-1||criterion.d(null,null,null,f)!=-1)throw new AssertionError("null sentinel");
  f.active=(PZ)Proxy.newProxyInstance(PZ.class.getClassLoader(),new Class[]{PZ.class},(p,m,a)->{if(m.getName().equals("ayn"))return 6967;throw new AssertionError(m);});
  if(criterion.d(null,null,null,f)!=6967)throw new AssertionError("actual PZ");
  System.out.println("PASS eJn current fight/null PZ/current PZ spell reference");
 }
}

import java.nio.ByteBuffer;
/** Offline TC scheduling with actual eVy effect317002 and Th test callback. */
public class ProbeNativeEffectTimer {
 static class Callback extends Th {
  public long biD(){return 7;}
  protected void b(TA value){}
  protected int biE(){return 0;}
  protected void eR(ByteBuffer buffer){}
  protected void e(ST value,ByteBuffer buffer){}
 }
 public static void main(String[] args) throws Exception {
  apw.bGL().dd("jar:file:"+java.nio.file.Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  eVv effect=(eVv)bcA.dcX().AH(317002);
  Tt nativeTimer=effect.en((short)1);
  Ts regular=new TC().a(new Callback(),nativeTimer,true,false,(short)3);
  Ts extension=new TC().a(new Callback(),Tt.pz(1).br(true),true,false,(short)3);
  Ts end=new TC().a(new Callback(),Tt.pz(1).bq(true),true,false,(short)3);
  Ts passed=new TC().a(new Callback(),nativeTimer,false,false,(short)3);
  for(Ts timer:new Ts[]{regular,extension,end,passed})
   System.out.println(timer.OO()+","+timer.biO()+","+timer.biN());
 }
}

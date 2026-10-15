import java.nio.*;
import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
/** Original native Tc parser/enrollment and aER creation-group closure, without UI or services. */
public class ProbeNativeReconnectSummonQueue {
 static class Step extends aET {
  final Runnable operation;
  Step(Runnable operation){super(1,0,0);this.operation=operation;}
  protected long cby(){operation.run();return 0;}
  protected void cbj(){}
 }
 static Tc table(){
  fce source=(fce)Proxy.newProxyInstance(fce.class.getClassLoader(),new Class[]{fce.class},(o,m,a)->m.getName().equals("d")?1:null);
  fev stats=(fev)Proxy.newProxyInstance(fev.class.getClassLoader(),new Class[]{fev.class},(o,m,a)->m.getName().equals("rI")?false:0);
  return new Tc(new feq(source,stats));
 }
 static int load(Tc tc,byte[] payload){
  ByteBuffer b=ByteBuffer.wrap(payload);b.getShort();b.getInt();int phase=b.get();b.getLong();tc.clear();tc.a(null,b);return phase;
 }
 static void birth(Tc tc,long actor){
  SQ options=new SQ();options.a(SR.pv(0));options.pt(0);options.ej(100);
  tc.a(actor,(short)0,options);
 }
 static long count(Tc tc,long actor){return Arrays.stream(tc.bsw.bhH().toArray()).filter(id->id==actor).count();}
 public static void main(String[]args)throws Exception{
  byte[] baseline=Files.readAllBytes(Path.of(args[0])), full=Files.readAllBytes(Path.of(args[1]));
  long actor=Long.parseLong(args[2]);
  Tc initial=table();if(load(initial,baseline)!=0||initial.bik()!=-1||count(initial,actor)!=0)throw new AssertionError("INITIAL projection must omit birth and current member");
  // The old full baseline/recovery is followed by delayed native enrollment.
  Tc old=table();load(old,full);birth(old,actor);
  if(count(old,actor)!=2)throw new AssertionError("old enrollment did not reproduce duplicate");
  Tc corrected=table();load(corrected,baseline);boolean[] enrolled={false};
  aER queue=new aER();queue.c(new Step(()->{birth(corrected,actor);enrolled[0]=true;}));
  queue.cbu(); // Original queue operation used by 13420/aUb.m.
  if(!enrolled[0]||count(corrected,actor)!=1)throw new AssertionError("creation did not enroll before immediate recovery");
  if(!queue.cbt().isEmpty())throw new AssertionError("creation queue did not close");
  if(load(corrected,full)!=1||count(corrected,actor)!=1||corrected.bil()!=actor||corrected.biw().big()!=3)throw new AssertionError("full recovery lost current summon or progress3");
  System.out.println("PASS original Tc INITIAL parser: no current substitution; old full-before-birth duplicates UID");
  System.out.println("PASS original aER closure enrolls before full recovery: current="+corrected.bil()+" progress="+corrected.biw().big()+" entries="+count(corrected,actor));
 }
}

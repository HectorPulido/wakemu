import java.lang.reflect.Proxy;
/** Actual eYQ.bbR keep/executed guard; Qs callback instrumented, no render. */
public class ProbeNativeAreaRemoval {
 static class Manager extends Qs {int calls; public Qq dp(long uid){return null;} public void b(Qq area){calls++;}}
 static class Runner extends eYQ { boolean executed; public boolean Ty(){return executed;} }
 public static void main(String[] args)throws Exception {
  eGM.a(null);
  for(boolean keep:new boolean[]{false,true})for(boolean executed:new boolean[]{false,true}){
   Manager manager=new Manager();Runner r=new Runner();r.executed=executed;
   PN context=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(o,m,a)->{
    if(m.getName().equals("baf"))return manager;
    throw new UnsupportedOperationException(m.getName());});
   ProbeNativeSummonDescriptor.set(r,"bfw",context);
   ProbeNativeSummonDescriptor.set(r,"oAP",new ProbeNativeAreaIdentity.Hour(new Qr().oK(1546).b(anD.bEz()).oN(1)));
   ProbeNativeSummonDescriptor.set(r,"rGS",keep);
   r.bbR();
   if(manager.calls!=(!keep&&executed?1:0))throw new AssertionError("native keep guard");
  }
  System.out.println("PASS native eYQ.bbR keep/executed matrix4cases");
 }
}

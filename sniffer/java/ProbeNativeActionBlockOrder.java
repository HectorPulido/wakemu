import java.util.*;
/** Original aER/aEV FIFO contract behind cvG13420 and cjU12873.
 * No graphics, network, invented transport ACK or timing delay.
 */
public final class ProbeNativeActionBlockOrder {
 static final List<String> observed=new ArrayList<>();
 static class Held extends aET {
  Held(){super(11,1,0);}
  protected long cby(){observed.add("damage-start");return -1;}
  protected void cbj(){}
  void finish(){observed.add("damage-finish");cbh();}
 }
 static class Snapshot extends aET {
  Snapshot(int id){super(id,2,0);}
  protected long cby(){observed.add("snapshot");return 0;}
  protected void cbj(){}
 }
 public static void main(String[]args){
  aER queue=new aER();Held damage=new Held();queue.c(damage);queue.cbu();
  queue.c(new Snapshot(12));queue.cbu();
  if(!observed.equals(List.of("damage-start")))throw new AssertionError(observed);
  damage.finish();
  if(!observed.equals(List.of("damage-start","damage-finish","snapshot")))throw new AssertionError(observed);
  if(!queue.cbt().isEmpty())throw new AssertionError("Queue not drained");
  System.out.println("PASS original aER/aEV: next snapshot block waits for damage cbh, no network ACK; "+observed);
 }
}

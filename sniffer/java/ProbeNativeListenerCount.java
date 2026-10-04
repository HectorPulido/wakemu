/** Exercises the actual Qe.aX depletion gate; retained status is an explicit fixture. */
public class ProbeNativeListenerCount {
 static class Listener extends eYg {
  boolean removed;
  Listener(int count){bfB=count;}
  public boolean Ty(){return true;}
  public void bbN(){removed=true;}
  int count(){return bfB;}
 }
 static void check(int initial,boolean accepted,int expected,boolean removal){
  Listener listener=new Listener(initial);listener.aX(accepted);
  if(listener.count()!=expected||listener.removed!=removal)
   throw new AssertionError(initial+" accepted="+accepted+" count="+listener.count()+" removed="+listener.removed);
 }
 public static void main(String[]args){
  check(2,true,1,false);check(1,true,0,true);check(0,true,0,true);
  check(-1,true,-1,false);check(1,false,1,false);
  System.out.println("native Qe.aX: accepted decrements positive count; zero removes; negative unlimited; rejected unchanged");
 }
}

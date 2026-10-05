import java.util.*;
/** aEV removes forced script actions by cbc identity, not object identity. */
public final class ProbeNativeForcedActionIdentity {
 static class Action extends aET {
  final String name;int executions;
  Action(int id,String name){super(id,1,0);this.name=name;}
  protected long cby(){executions++;return -1;}
  protected void cbj(){}
 }
 static void check(boolean duplicate) {
  aEV group=new aEV();Action animation=new Action(228,"animation");Action effect=new Action(duplicate?228:229,"effect");
  group.b(animation);group.b(effect);animation.a(group);effect.a(group);animation.dP(true);
  group.a(effect,false);
  if(duplicate) {
   if(group.cbC().contains(animation)||!group.cbC().contains(effect))throw new AssertionError("Expected wrong first matching removal");
   group.a(effect,false);
   if(effect.executions!=2||!group.cbC().isEmpty())throw new AssertionError("Native repeat caused by retained duplicate");
   System.out.println("PASS duplicate cbc228 forced effect removes ANIMATION then repeats EFFECT: executions2");
  } else {
   if(!group.cbC().contains(animation)||group.cbC().contains(effect))throw new AssertionError("Unique identity removal");
   if(effect.executions!=1)throw new AssertionError("Unique execution");
   System.out.println("PASS unique cbc228/229 removes EFFECT once; animation remains queued");
  }
 }
 public static void main(String[]args){check(true);check(false);}
}

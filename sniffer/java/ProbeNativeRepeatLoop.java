import java.lang.reflect.*;
/** Actual eXN cap/loop/stop machinery with an explicit per-iteration counter feed. */
public class ProbeNativeRepeatLoop {
 static final class Runner extends eXN {
  int requested,calls,emptyAt;boolean stop;
  protected int G(Qe source){return requested;}
  protected boolean H(Qe source){return stop;}
  public boolean bbz(){return true;}public boolean bbA(){return false;}public boolean bbB(){return true;}
  public anS bEs(){return null;}public Qe bbn(){return new Runner();}
  protected void l(eZR source){calls++;try{Field f=eZM.class.getDeclaredField("rIO");f.setAccessible(true);f.setInt(this,calls==emptyAt?1:0);}catch(Exception e){throw new RuntimeException(e);}}
  int run(int count,boolean stop,int emptyAt){requested=count;this.stop=stop;this.emptyAt=emptyAt;calls=0;C(null);c(null,false);return calls;}
 }
 public static void main(String[]args){Runner runner=new Runner();
  if(runner.run(30,false,0)!=12||runner.run(0,false,0)!=0||runner.run(-3,false,0)!=0||runner.run(12,true,2)!=2)throw new AssertionError("native eXN loop mismatch");
  PT pt=new PT();if(pt.bas()!=0)throw new AssertionError();pt.bap();pt.bap();if(pt.bas()!=2)throw new AssertionError();pt.clear();if(pt.bas()!=0)throw new AssertionError();
  System.out.println("PASS actual eXN cap12/zero/negative/stopafter2 and PT.bap/bas counter");
 }
}

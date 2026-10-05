import java.util.*;
/** Native Qf/eZX null-source selection; does not prove a turn producer. */
public class ProbeNativeTurnEndSelection {
 static BitSet bits(){BitSet b=new BitSet();b.set(1001);return b;}
 static final class Effect extends eYg {
  final boolean reverse,global; int fired; boolean nullSource;
  Effect(boolean r,boolean g){reverse=r;global=g;bfx=901;}
  public boolean a(eVl f){return false;}
  public boolean aZB(){return false;}
  public boolean aZx(){return global;}
  public boolean aZw(){return reverse;}
  public BitSet aZG(){return null;} public BitSet aZH(){return null;}
  public BitSet aZI(){return null;} public BitSet aZJ(){return null;}
  public BitSet aZK(){return null;} public BitSet aZL(){return bits();}
  public BitSet bbu(){return null;} public BitSet bbv(){return bits();}
  public void k(Qe source){fired++;nullSource=source==null;}
 }
 static final class Manager extends Qf {
  final Qi dispatch=new eZX(this); public Qi bci(){return dispatch;}
  void add(Effect e){bfT.put(e.LV(),e);}
 }
 public static void main(String[]args){
  for(int mode=0;mode<3;mode++)for(byte channel:new byte[]{6,60,61}){
   Manager m=new Manager();Effect e=new Effect(mode==1,mode==2);m.add(e);
   m.a(bits(),null,channel);int expected=channel==(mode==0?6:mode==1?60:61)?1:0;
   if(e.fired!=expected||(expected==1&&!e.nullSource))throw new AssertionError(mode+":"+channel+"="+e.fired);
   System.out.println("mode="+mode+" channel="+channel+" selected="+e.fired+" nullSource="+e.nullSource);
  }
 }
}

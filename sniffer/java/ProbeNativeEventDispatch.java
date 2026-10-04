import java.util.*;
public class ProbeNativeEventDispatch {
 static BitSet bits(int...ids){BitSet b=new BitSet();for(int id:ids)b.set(id);return b;}
 static final class Effect extends eYg {
  final boolean bypass,silent; int fired; final BitSet mask=bits(1001);
  Effect(boolean bypass,boolean silent,long uid){this.bypass=bypass;this.silent=silent;this.bfx=uid;}
  public boolean a(eVl flag){return flag==eVl.rwy&&bypass;}
  public boolean aZB(){return silent;}
  public boolean aZx(){return false;}
  public boolean aZw(){return false;}
  public BitSet aZG(){return mask;}
  public BitSet aZH(){return null;}
  public BitSet aZI(){return null;}
  public BitSet aZJ(){return null;}
  public BitSet bbu(){return null;}
  public BitSet bbv(){return null;}
  public void k(Qe trigger){fired++;}
 }
 static final class Manager extends Qf {
  final Qi dispatcher=new eZX(this);
  public Qi bci(){return dispatcher;}
  void add(Effect e){bfT.put(e.LV(),e);}
 }
 public static void main(String[]args){
  for(boolean bypass:new boolean[]{false,true})for(boolean silent:new boolean[]{false,true}){
   Manager manager=new Manager();Effect retained=new Effect(bypass,false,901);manager.add(retained);
   Effect trigger=new Effect(false,silent,800);
   boolean result=manager.a(bits(1001),trigger,(byte)1);
   System.out.println("bypass="+bypass+" silent="+silent+" selected="+result+" fired="+retained.fired);
   if(retained.fired!=(silent&&!bypass?0:1))throw new AssertionError();
  }
 }
}

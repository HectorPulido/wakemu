/** Inspect actual fresh PC WP observers, no gameplay or callback invocation. */
public class ProbeNativeFreshPropertyListeners {
 public static void main(String[]args){
  try{
   biB pc=new biB(false);PA wp=pc.e(ffw.sgF);
   var classes=wp.aZi().stream().map(p->p.getClass().getName()).toList();
   if(!classes.equals(java.util.List.of("bkq","biB")))throw new AssertionError(classes.toString());
   System.out.println("PASS actual fresh WP observers bkq/biB; bks.sgF branch6 UI timeline, bnj characteristics refresh");
   System.exit(0);
  }catch(Throwable e){e.printStackTrace();System.exit(1);}
 }
}

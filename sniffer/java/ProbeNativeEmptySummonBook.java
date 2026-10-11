import java.util.ArrayList;
/** bje.aQc's actual bPD initialization accepts an explicit empty ability list. */
public class ProbeNativeEmptySummonBook {
 public static void main(String[] args) {
  for(short level:new short[]{0,1,38,128,230,32767}) {
   bPD book=new bPD();
   book.a(new ArrayList<ayB<bPK>>(),level,null);
   if(book.dos().iterator().hasNext()) throw new AssertionError("Empty native book acquired an action");
  }
  System.out.println("Actual native bPD empty book initialization6/6PASS");
 }
}

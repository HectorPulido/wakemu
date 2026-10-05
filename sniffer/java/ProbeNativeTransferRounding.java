/** Native eYy uses int product then GS.B/UP.bt/GS.C, not nearest rounding. */
public class ProbeNativeTransferRounding {
 public static void main(String[]args) {
  float scaled=(float)(Integer.MAX_VALUE*100)/100f;
  if(GS.B(scaled)!=-1)throw new AssertionError("int overflow before float conversion");
  if(GS.B(-1.5f)!=-2||GS.C(-1.5f)!=-1)throw new AssertionError("signed floor/ceil");
  int low=0,high=0;
  for(int i=0;i<256;i++) {
   int x=UP.bt(-1.5f);
   if(x==-2)low++;else if(x==-1)high++;else throw new AssertionError("stochastic bounds");
  }
  if(low==0||high==0)throw new AssertionError("UP.bt must vary with fractional probability");
  System.out.println("PASS native transfer int overflow, signed floor/ceil, stochastic UP.bt both outcomes");
 }
}

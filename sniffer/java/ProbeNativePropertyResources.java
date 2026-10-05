/** eWt calls PA.aZg for AP/MP and PA.aZk for WP: verify real PA behavior. */
public class ProbeNativePropertyResources {
 public static void main(String[]args)throws Exception {
  for(ffw kind:new ffw[]{ffw.sgD,ffw.sgE}) {
   fff resource=new fff(kind,0,10);resource.or(10);resource.on(6);
   int minimum=resource.aYW();resource.aZg();
   if(resource.aYT()!=minimum)throw new AssertionError("aZg must set current to minimum");
   resource.on(4);
   if(resource.aYT()!=4)throw new AssertionError("aZg must not permanently freeze resource");
  }
  fff wp=new fff(ffw.sgF,0,10);wp.or(10);wp.on(6);
  int[] calls={0};wp.a(resource->{calls[0]++;});
  wp.aZk();
  if(calls[0]!=1||wp.aYT()!=6)throw new AssertionError("aZk must notify listener without resetting WP");
  System.out.println("PASS PA.aZg AP/MP -> minimum, remains mutable; PA.aZk WP -> listeners, no direct reset");
 }
}

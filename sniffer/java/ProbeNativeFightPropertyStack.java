public class ProbeNativeFightPropertyStack {
 public static void main(String[]args){
  PB<ffe> stack=new eHN<>();ffe property=ffe.Ua(11);
  if(property==null)throw new AssertionError("known property11");
  if(stack.c(property)!=1||stack.c(property)!=2||!stack.a(property))throw new AssertionError("two sources");
  if(stack.d(property)!=1||!stack.a(property))throw new AssertionError("first source removed");
  if(stack.d(property)!=0||stack.a(property))throw new AssertionError("second source removed");
  if(stack.d(property)!=0)throw new AssertionError("absent removal");
  stack.a(property,(byte)127);
  if(stack.c(property)!=-128||!stack.a(property))throw new AssertionError("signed byte overflow");
  if(stack.d(property)!=127||!stack.a(property))throw new AssertionError("wrapped subtraction");
  System.out.println("PASS native PB property stack: overlapping sources, removal, absent, byte overflow");
 }
}

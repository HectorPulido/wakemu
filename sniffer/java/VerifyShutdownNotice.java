/** Native packet decoder plus disconnect-handler switch mapping, offline. */
public class VerifyShutdownNotice {
 public static void main(String[] args)throws Exception{
  Np packet=new Np();if(!packet.dp(new byte[]{16})||packet.d()!=18||!packet.aWD().name().equals("DISCONNECTION_REASON_SERVER_SHUTDOWN"))throw new AssertionError("Native shutdown reason mismatch");
  Class<?> dispatch=Class.forName("cgJ");var field=dispatch.getDeclaredField("mhO");field.setAccessible(true);int[]cases=(int[])field.get(null);if(cases[packet.aWD().ordinal()]!=12)throw new AssertionError("cgI serverShutdown branch mismatch");
  System.out.println("Np18/Uw16 -> cgI case12 disconnection.serverShutdown verified");
 }
}

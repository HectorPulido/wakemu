public final class DropinNetworkGuardTest{
 public static void main(String[]args)throws Exception{
  SecurityManager guard=System.getSecurityManager();if(guard==null)throw new AssertionError("Guard missing");
  guard.checkConnect("127.0.0.1",18081);
  for(String host:new String[]{"ankama.com","wakfu.com","8.8.8.8"}){
   try{guard.checkConnect(host,-1);throw new AssertionError("DNS allowed: "+host);}catch(SecurityException expected){}
   try{guard.checkConnect(host,443);throw new AssertionError("Socket allowed: "+host);}catch(SecurityException expected){}
  }
  System.out.println("Private-server guard verified without external network requests");
 }
}

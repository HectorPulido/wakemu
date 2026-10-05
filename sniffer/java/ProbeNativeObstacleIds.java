import java.lang.reflect.*;
public class ProbeNativeObstacleIds {
 static QK actor(byte id){return (QK)Proxy.newProxyInstance(QK.class.getClassLoader(),new Class[]{QK.class},(p,m,a)->{
  if(m.getName().equals("bcN"))return id;
  if(m.getName().equals("toString"))return "owned-actor";
  Class<?> t=m.getReturnType(); if(t==boolean.class)return false;if(t==byte.class)return (byte)0;if(t==short.class)return (short)0;if(t==int.class)return 0;if(t==long.class)return 0L;if(t==float.class)return 0f;if(t==double.class)return 0d;return null;
 });}
 public static void main(String[] args){
  for(int n:new int[]{2,8}){QI map=new QI();for(int i=0;i<=n;i++){QK a=actor((byte)i);map.i(a);if(map.O((byte)i)!=a)throw new AssertionError("index "+i);} }
  QI old=new QI();QK first=actor((byte)1),second=actor((byte)1);old.i(first);old.i(second);if(old.O((byte)1)!=second)throw new AssertionError("collision");
  System.out.println("PASS: native QI unique byte indices 2/8 NPC; shared byte1 replaces original obstacle");
 }
}

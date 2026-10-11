import java.lang.reflect.Proxy;
/** Actual installed faI comparison over explicitly supplied PA operands. */
public class ProbeNativeHealthTargetOrdering {
 static PV actor(boolean present, int current, int maximum) {
  PA pa = new fff(ffw.sgC, 0, Integer.MAX_VALUE) {
   public int aYS() { return current; }
   public int aYU() { return maximum; }
  };
  return (PV) Proxy.newProxyInstance(PV.class.getClassLoader(), new Class[]{PV.class}, (p,m,a) -> {
   if (m.getName().equals("a") && a.length == 1 && a[0] == ffw.sgC) return present;
   if (m.getName().equals("b") && a.length == 1 && a[0] == ffw.sgC) return pa;
   throw new UnsupportedOperationException(m.getName());
  });
 }
 public static void main(String[] args) {
  int[][] operands = {{0,0},{0,1},{1,0},{-1,0},{1,2},{2,4},{1,-2},{-1,2},
   {Integer.MAX_VALUE,Integer.MAX_VALUE},{Integer.MIN_VALUE,Integer.MAX_VALUE},
   {16777217,16777216},{16777216,16777217},{0,-1},{1,3},{2,3}};
  faI comparator = new faI();
  for (int a = -1; a < operands.length; a++) for (int b = -1; b < operands.length; b++) {
   int[] x = a < 0 ? new int[]{0,0} : operands[a];
   int[] y = b < 0 ? new int[]{0,0} : operands[b];
   int comparison = comparator.c(actor(a >= 0,x[0],x[1]), actor(b >= 0,y[0],y[1]));
   System.out.println(a+"\t"+b+"\t"+comparison);
  }
 }
}

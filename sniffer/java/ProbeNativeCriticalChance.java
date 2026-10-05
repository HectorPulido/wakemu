public class ProbeNativeCriticalChance {
 public static void main(String[]args){
  ffw pc=ffw.sgI;
  if(pc.aKg()!=9||!pc.name().equals("FEROCITY"))throw new AssertionError();
  fqX category=fqX.valueOf("CRITICAL_CHANCE");
  if(category.glv()!=pc)throw new AssertionError();
  System.out.println("PASS critical chance PC="+pc.aKg()+" name="+pc.name()+" category="+category.name());
  System.out.println("native bounds/base="+pc.aZo()+","+pc.aZp()+","+pc.aZq()+","+pc.aZr()+","+pc.aZs());
  if(pc.aZo()!=-1000||pc.aZp()!=1000||pc.aZq()!=-1000||pc.aZr()!=1000||pc.aZs()!=3)throw new AssertionError();
  // Original UI formatting marks this characteristic as a direct percentage.
  bll display=new bll((short)1,pc,37,37);
  Object value=display.eH("value");
  if(value==null||!value.toString().contains("37")||!value.toString().contains("%"))throw new AssertionError("UI:"+value);
  System.out.println("PASS UI percentage "+value);
 }
}

import java.lang.reflect.*;
import java.util.*;
import java.util.HexFormat;

/** Offline exact eZE additional codec and eWB guard truth table. */
public final class ProbeNativeCarryDelivery {
    static void field(Object object, Class<?> owner, String name, Object value) throws Exception {
        Field field=owner.getDeclaredField(name);field.setAccessible(true);field.set(object,value);
    }
    public static void main(String[] args) throws Exception {
        Method codec=eZE.class.getDeclaredMethod("b",iP.class);codec.setAccessible(true);
        for(int[] cell:new int[][]{{0,0,0},{7,-9,-1},{Integer.MIN_VALUE,Integer.MAX_VALUE,-32768}})
            for(boolean qcl:new boolean[]{false,true}) {
                eZE runner=new eZE();field(runner,Qe.class,"bft",new aBn(cell[0],cell[1],(short)cell[2]));
                field(runner,eZE.class,"qcl",qcl);
                iP builder=iN.QQ();codec.invoke(runner,builder);
                System.out.println("codec "+cell[0]+" "+cell[1]+" "+cell[2]+" "+qcl+" "+HexFormat.of().formatHex(builder.QA().toByteArray()));
            }
        Method apply=eWB.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);
        int checked=0;
        for(int bits=0;bits<64;bits++)for(boolean bypass:new boolean[]{false,true})for(boolean same:new boolean[]{false,true}) {
            final int flags=bits;boolean[] invoked={false};
            PV target=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class,eHH.class,eHg.class},(p,m,a)->switch(m.getName()) {
                case "a" -> a[0]==ffe.seN?(flags&1)!=0:a[0]==ffe.sdI?(flags&2)!=0:a[0]==ffe.sfA?(flags&8)!=0:a[0]==ffe.sfB?(flags&32)!=0:false;
                case "bcM" -> (byte)(same?0:1);
                case "bcz","bcA" -> 0;
                case "bcB" -> (short)0;
                default -> throw new AssertionError("Unexpected target "+m);
            });
            PV caster=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class,eHG.class,eHg.class},(p,m,a)->switch(m.getName()) {
                case "a" -> { if(a[0] instanceof eHH){invoked[0]=true;yield true;} yield a[0]==ffe.sfA?(flags&4)!=0:a[0]==ffe.sfB?(flags&16)!=0:false; }
                case "bcM" -> (byte)0;
                case "Sn" -> 7L;
                default -> throw new AssertionError("Unexpected caster "+m);
            });
            PN context=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(p,m,a)->null);
            eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->switch(m.getName()){case "a"->bypass;case "aZE"->0;case "fLb"->false;default->null;});
            eWB runner=new eWB();field(runner,Qe.class,"bfs",target);field(runner,Qe.class,"bfr",caster);
            field(runner,Qe.class,"bfw",context);field(runner,Qe.class,"bfp",definition);
            apply.invoke(runner,null,false);
            boolean expected=(flags&1)==0&&(bypass||((flags&2)==0&&(same?(flags&48)==0:(flags&12)==0)));
            if(invoked[0]!=expected)throw new AssertionError("Native eWB gate "+bits+" "+bypass+" "+same);
            checked++;
        }
        System.out.println("PASS "+checked+" native eWB property/flag/affiliation combinations");
    }
}

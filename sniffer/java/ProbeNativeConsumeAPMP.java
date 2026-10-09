import java.lang.reflect.*;

/** Original eXm calculation and eWf signed-byte packing without catalogs. */
public final class ProbeNativeConsumeAPMP {
    static void set(Object o, Class<?> c, String field, Object value) throws Exception {
        Field f=c.getDeclaredField(field); f.setAccessible(true); f.set(o,value);
    }
    static int get(Object o,String field)throws Exception {
        Field f=eXm.class.getDeclaredField(field); f.setAccessible(true); return f.getInt(o);
    }
    public static void main(String[] args)throws Exception {
        for(int[] row:new int[][]{{6,3,1,0},{6,3,-1,-1},{0,0,1,1},{6,3,99,99},
                {200,3,-1,-1},{-1,3,-1,-1},{6,200,-1,-1}}) {
            PV actor=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},
                (p,m,a)->switch(m.getName()) {
                    case "c" -> a[0]==ffw.sgD?row[0]:row[1];
                    case "Sn" -> 7L;
                    case "bcz", "bcA" -> 0;
                    case "bcB" -> (short)0;
                    default -> null;
                });
            eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},
                (p,m,a)->m.getName().equals("a")&&a.length==3?row[(Integer)a[0]+2]:null);
            eXm parent=new eXm();set(parent,Qe.class,"bfr",actor);set(parent,Qe.class,"bfp",definition);
            parent.C(null);
            int ap=get(parent,"rDh"),mp=get(parent,"rDi");
            eWf cost=eWf.a(null,new fyQ((byte)ap,(byte)mp,(byte)0),actor);
            System.out.println("ROW "+row[0]+" "+row[1]+" "+row[2]+" "+row[3]+" "+ap+" "+mp
                +" "+cost.fMH()+" "+cost.fMG()+" "+cost.fMF()+" "+cost.d()+" EVENTS="+cost.bbw()+" SUPPRESS="+cost.aZB());
        }
        eWf cost=eWf.a(null,new fyQ((byte)1,(byte)0,(byte)0),null);
        set(cost,Qe.class,"bfx", 901L);
        System.out.println("PROTO="+java.util.HexFormat.of().formatHex(cost.aqv()));
        for(int[] row:new int[][]{{6,3,1,0},{6,3,6,3},{0,0,0,0}}) {
            fff ap=new fff(ffw.sgD,0,6), mp=new fff(ffw.sgE,0,3);
            ap.or(6);mp.or(3);ap.on(row[0]);mp.on(row[1]);
            PV actor=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},
                (p,m,a)-> {
                    if(m.getName().equals("c")&&a.length==1) return a[0]==ffw.sgD?ap.aYS():mp.aYS();
                    if(m.getName().equals("b")&&a.length==1&&a[0] instanceof PC) return a[0]==ffw.sgD?ap:mp;
                    if(m.getName().equals("a")&&a.length==1&&a[0] instanceof PC) return true;
                    if(m.getName().equals("Sn"))return 7L;
                    Class<?> t=m.getReturnType();
                    if(t==boolean.class)return false;if(t==int.class)return 0;
                    if(t==short.class)return (short)0;if(t==byte.class)return (byte)0;
                    if(t==long.class)return 0L;if(t==float.class)return 0f;
                    return null;
                });
            eWf paid=eWf.a(null,new fyQ((byte)row[2],(byte)row[3],(byte)0),actor);
            paid.e(actor);
            Method execute=eWf.class.getDeclaredMethod("c",Qe.class,boolean.class);
            execute.setAccessible(true);execute.invoke(paid,null,false);
            set(paid,eZR.class,"rEj",true);
            System.out.println("PAID "+row[0]+" "+row[1]+" "+row[2]+" "+row[3]
                +" AFTER="+ap.aYS()+","+mp.aYS()+" UID="+paid.LV()+" BASE="+paid.Qq()
                +" STATUS="+paid.cYh()+" PROTO="+java.util.HexFormat.of().formatHex(paid.aqv()));
        }
        System.exit(0);
    }
}

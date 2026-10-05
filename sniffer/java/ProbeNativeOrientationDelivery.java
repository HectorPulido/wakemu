import java.lang.reflect.*;
import java.nio.file.*;
/** Decode server eWF payload and execute original13497/12613 action queues. */
public class ProbeNativeOrientationDelivery {
    static class Actor implements InvocationHandler {
        final long id; int direction;
        Actor(long id,int direction){this.id=id;this.direction=direction;}
        PV proxy(){return (PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},this);}
        public Object invoke(Object proxy,Method method,Object[] args){
            return switch(method.getName()) {
                case "Sn" -> id;
                case "bcy" -> aAS.wL(direction);
                case "a" -> { if(args[0] instanceof aAS)direction=((aAS)args[0]).wp(); yield method.getReturnType()==boolean.class?false:null; }
                default -> {Class<?> type=method.getReturnType();yield type==boolean.class?false:type==int.class?0:type==long.class?0L:type==short.class?(short)0:null;}
            };
        }
    }
    static class Runner extends eWF {
        protected void c(Qe previous,boolean active){System.out.println("native eWF.c value="+getValue()+" target="+(bbc()==null?null:bbc().Sn()));super.c(previous,active);}
    }
    static class Observe extends aTR {
        Observe(eZR runner){super(1,0,7,303,runner);}
        void execute(){super.cbj();}
    }
    static class Complete extends aVo {
        final buQ world;
        Complete(eZR runner,PV caster,PV target){super(1,0,303,7,runner,false);
            PW actors=(PW)Proxy.newProxyInstance(PW.class.getClassLoader(),new Class[]{PW.class},(p,m,a)->m.getName().equals("de")?(((Long)a[0])==caster.Sn()?caster:((Long)a[0])==target.Sn()?target:null):null);
            PN context=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(p,m,a)->m.getName().equals("bae")?actors:m.invoke(bcz.dcW(),a));
            world=(buQ)Proxy.newProxyInstance(buQ.class.getClassLoader(),new Class[]{buQ.class},(p,m,a)->switch(m.getName()){case "bbg"->context;case "equals"->p==a[0];default->null;});
        }
        protected buQ cjD(){return world;}
    }
    static void set(Object object,String field,Object value)throws Exception {
        Field f=Qe.class.getDeclaredField(field);f.setAccessible(true);f.set(object,value);
    }
    public static void main(String[] args)throws Exception {
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        System.out.println("native spell7318 script="+bPS.elL().IP(7318).cbH());
        byte[] payload=Files.readAllBytes(Path.of(args[0]));
        for(boolean complete:new boolean[]{false,true}) {
            Actor casterState=new Actor(7,0),targetState=new Actor(-7,0);
            PV caster=casterState.proxy(),target=targetState.proxy();
            eWF runner=new Runner();runner.lV(303);runner.a(bcz.dcW());
            if(runner.ds(payload)==null)throw new AssertionError("native decode failed");
            eVn definition=bcA.dcX().AH(iN.bf(payload).Qs());
            System.out.println("definition="+definition.aZE()+" mode20="+definition.a(0,(short)20,eVh.rpA));
            set(runner,"bfp",definition);
            set(runner,"bfr",caster);set(runner,"bfs",target);
            int decoded=runner.getValue();
            if(decoded!=5)throw new AssertionError("value decode");
            System.out.println("before Ty="+runner.Ty()+" aZN="+runner.aZN()+" bbW="+runner.bbW());
            if(complete){Complete action=new Complete(runner,caster,target);action.cYb();action.fe(target.Sn());action.iD(caster.Sn());aER queue=new aER();queue.c(action);queue.cbu();if(!queue.cbt().isEmpty())throw new AssertionError("queue not drained");
                // Graphics action303 completes asynchronously; invoke the original
                // completion callback explicitly without claiming a rendered frame.
                action.cbj();}
            else{runner.bbq();new Observe(runner).execute();}
            int expected=complete?5:0;
            if(targetState.direction!=expected)throw new AssertionError("direction="+targetState.direction);
            System.out.println("opcode="+(complete?12613:13497)+" decodedDirection="+decoded+" actualDirection="+targetState.direction+" gameplayEnabled="+runner.bbs());
        }
        System.out.println("PASS original eWF delivery:13497 leaves facing unchanged;12613 applies decoded facing");
    }
}

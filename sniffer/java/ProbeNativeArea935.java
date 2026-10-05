import java.lang.reflect.*;import java.util.*;import java.nio.file.*;
public class ProbeNativeArea935 {
 static class Manager extends Qs {List<Qq> rows=new ArrayList<>(),removed=new ArrayList<>();PV caster;public Qq dp(long id){return null;}public Collection<Qq> bdm(){return rows;}public void a(Qq q,PV p){removed.add(q);caster=p;}}
 static void set(Object o,String n,Object v)throws Exception{ProbeNativeSummonDescriptor.set(o,n,v);}
 public static void main(String[]args)throws Exception{
 eGM.a(null);for(int reference:new int[]{781,999,-1}){
 eXS runner=new eXS();Manager manager=new Manager();
 for(int ref:new int[]{781,781,999}){var area=new ProbeNativeAreaCallbacks.Area();set(area,"bgV",(long)ref);set(area,"bhh",false);manager.rows.add(area);}
 PV caster=ProbeNativeEffectUIDs.actor(7);
 PN context=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(o,m,a)->switch(m.getName()){case"baf"->manager;case"baa"->null;default->throw new UnsupportedOperationException(m.getName());});
 eVv definition=(eVv)Proxy.newProxyInstance(eVv.class.getClassLoader(),new Class[]{eVv.class},(o,m,a)->switch(m.getName()){case"fLb"->false;case"aZE"->300001;case"fKJ"->1;case"a"->reference;default->throw new UnsupportedOperationException(m.getName());});
 set(runner,"bfw",context);set(runner,"bfp",definition);set(runner,"bfr",caster);set(runner,"bft",new aBn(0,0,(short)0));set(runner,"bfD",true);set(runner,"bfx",999L);set(runner,"bfy",999L);
 runner.C(null);Method apply=eXS.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);apply.invoke(runner,null,false);
 if(manager.removed.size()!=(reference==781?2:reference==999?1:0))throw new AssertionError();
 if(!manager.removed.isEmpty()&&manager.caster!=caster)throw new AssertionError("actual caster");
 if(reference==781&&args.length>0){set(runner,"rEj",true);Files.write(Path.of(args[0]),runner.bca().toByteArray());}
 }System.out.println("PASS eXS935 all exact reference matches, no bcF/wildcard filter, actual caster");}
}

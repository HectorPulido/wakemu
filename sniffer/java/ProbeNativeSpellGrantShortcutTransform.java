import java.util.jar.*;
/** Loads and instantiates the transformed original class under actual JVM verification. */
public class ProbeNativeSpellGrantShortcutTransform {
    static class Book extends fyR<fyG> {
        boolean present;int adds;
        Book(){super((short)12,null,null,false,false,false);}
        public boolean f(fyG item){return present;}
        public boolean b(fyG item){present=true;adds++;return true;}
    }
    static class Registry extends fzf {
        int calls;
        public void aW(Integer reference){if(reference!=4604)throw new AssertionError("registry reference");calls++;}
    }
    static void set(Object object,Class<?> owner,String name,Object value)throws Exception{
        var field=owner.getDeclaredField(name);field.setAccessible(true);field.set(object,value);
    }
    static class Loader extends ClassLoader {
        Loader(){super(ProbeNativeSpellGrantShortcutTransform.class.getClassLoader());}
        Class<?> define(byte[] bytes){return defineClass("eWn",bytes,0,bytes.length);}
    }
    public static void main(String[] args)throws Exception {
        byte[] original;
        try(JarFile jar=new JarFile("client/lib/wakfu-client.jar")) {
            try(var in=jar.getInputStream(jar.getJarEntry("eWn.class"))){original=in.readAllBytes();}
        }
        byte[] transformed=NativeSpellGrantShortcutTransformer.transform(original);
        Class<?> type=new Loader().define(transformed);
        Object runner=type.getConstructor().newInstance();
        type.getMethod("fMO").invoke(runner); // Null actor follows the untouched original early return.
        var actor=(ProbeNativeSpellGrantShortcut.Actor)ProbeNativeSpellGrantShortcut.allocate(ProbeNativeSpellGrantShortcut.Actor.class);
        actor.controlled=true;
        var fight=(ProbeNativeSpellGrantShortcut.Fight)ProbeNativeSpellGrantShortcut.allocate(ProbeNativeSpellGrantShortcut.Fight.class);
        fight.registered=true;fight.actor=actor;actor.fight=fight;
        var manager=(ProbeNativeSpellGrantShortcut.Manager)ProbeNativeSpellGrantShortcut.allocate(ProbeNativeSpellGrantShortcut.Manager.class);
        manager.bar=new bOX(fyv.tuO,(byte)2);actor.manager=manager;
        bOS shortcut=bOS.a(fyw.tvb,4604,4604,1);
        if(!manager.bar.a(shortcut,(short)4))throw new AssertionError("shortcut setup");
        var spell=new ProbeNativeSpellGrantShortcut.Spell();spell.uid=4604;spell.reference=4604;spell.value=1;
        Book book=(Book)ProbeNativeSpellGrantShortcut.allocate(Book.class);Registry registry=new Registry();
        actor.book=book;actor.registry=registry;
        set(runner,Qe.class,"bfs",actor);set(runner,type,"rAY",spell);
        set(runner,type,"rAV",(byte)2);set(runner,type,"rAW",(short)0);set(runner,type,"hXV",4604);
        for(int i=0;i<50;i++)type.getMethod("fMO").invoke(runner);
        if(book.adds!=1||registry.calls!=50||actor.calls!=0||manager.bar.a(shortcut)!=4)
            throw new AssertionError("native grant book, registry or existing shortcut changed");
        try{NativeSpellGrantShortcutTransformer.transform(transformed);throw new AssertionError("double transform accepted");}
        catch(IllegalStateException expected){}
        System.out.println("PASS actual JVM verifies and executes transformed original eWn.fMO; exactly one call replaced; duplicate transformation rejected");
        System.out.println("PASS 50 complete original fMO executions retain book insertion and all registry refreshes, with no duplicate shortcut insertion");
    }
}

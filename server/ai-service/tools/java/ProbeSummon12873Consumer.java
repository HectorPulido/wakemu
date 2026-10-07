import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

/** Detached differential: real bje/eHD summon through the real cjU 12873 consumer. */
public final class ProbeSummon12873Consumer {
  static void set(Object target, Class<?> owner, String field, Object value) throws Exception {
    Field f = owner.getDeclaredField(field);
    f.setAccessible(true);
    f.set(target, value);
  }

  public static void main(String[] args) throws Exception {
    if (args.length != 1) throw new IllegalArgumentException("usage: ProbeSummon12873Consumer packet.bin");
    apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
    fyZ.guX().a(new bbV());
    Method convert = bbo.class.getDeclaredMethod("a", aMb.class, short.class);
    convert.setAccessible(true);
    Map<Integer, blj> wanted = new HashMap<>();
    apw.bGL().a(new aMb(), new apB<aMb>() {
      public void load(aMb row) {
        if (row.d() == 1153 || row.d() == 5525) {
          try { wanted.put(row.d(), (blj) convert.invoke(null, row, (short) row.d())); }
          catch (Exception e) { throw new RuntimeException(e); }
        }
      }
    });

    bje caster = bje.dsi();
    caster.dA(7);
    caster.c(wanted.get(5525));
    caster.bz((short) 20);
    caster.dpQ();
    bje summon = bje.dsi();
    summon.dA(901);
    summon.c(wanted.get(1153));
    summon.bz((short) 20);
    summon.dpQ();
    Method prepare = bje.class.getDeclaredMethod("drd");
    prepare.setAccessible(true);
    prepare.invoke(summon);
    eHD descriptor = new eHD((short) 1153, "", -1, (short) 20);
    descriptor.lZ(901);
    descriptor.M((byte) 0);
    descriptor.a(aAS.dyw);
    descriptor.au((byte) 0);
    descriptor.a(summon, caster);
    if (summon.fqd() != descriptor) throw new AssertionError("eHD descriptor not attached to live summon");

    int beforeHp = summon.c(ffw.sgC);
    int beforeAp = summon.c(ffw.sgD);
    int beforeMp = summon.c(ffw.sgE);
    int beforeWp = summon.c(ffw.sgF);
    System.out.println("before actor=" + summon.Sn() + " hp=" + beforeHp + " ap=" + beforeAp + " mp=" + beforeMp + " wp=" + beforeWp + " ref=" + descriptor.dsr() + " level=" + descriptor.cmZ());

    // Allocate only the registry container: invoking cjU.b itself is the real
    // opcode consumer path; the detached probe does not construct UI/rendering.
    sun.misc.Unsafe unsafe;
    Field unsafeField = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
    unsafeField.setAccessible(true);
    unsafe = (sun.misc.Unsafe) unsafeField.get(null);
    buH fight = (buH) unsafe.allocateInstance(buH.class);
    fdt<eGj> roster = new fdt<>();
    gnu.trove.map.hash.TLongObjectHashMap<eGj> actors = new gnu.trove.map.hash.TLongObjectHashMap<>();
    actors.put(901L, summon);
    set(roster, fdt.class, "saq", actors);
    set(fight, fcb.class, "rRN", roster);
    cjU consumer = new cjU();
    set(consumer, cjm.class, "jsz", fight);

    cuU packet = new cuU();
    // cuU.dp deliberately returns false after filling its opaque payload (see bytecode).
    packet.dp(Files.readAllBytes(Path.of(args[0])));
    if (packet.bhe() != 1 || packet.KU() != 901L)
      throw new AssertionError("outer fight/UID=" + packet.bhe() + "/" + packet.KU());
    consumer.b(packet);

    int afterHp = summon.c(ffw.sgC);
    int afterAp = summon.c(ffw.sgD);
    int afterMp = summon.c(ffw.sgE);
    int afterWp = summon.c(ffw.sgF);
    System.out.println("after actor=" + summon.Sn() + " hp=" + afterHp + " ap=" + afterAp + " mp=" + afterMp + " wp=" + afterWp + " ref=" + descriptor.dsr() + " level=" + descriptor.cmZ());
    if (afterHp != 17 || afterAp != 4 || afterMp != 2 || afterWp != 2)
      throw new AssertionError("12873 consumer did not apply expected eHj resource snapshot");
    if (summon.fqd() != descriptor || descriptor.dsr() != 1153 || descriptor.cmZ() != 20)
      throw new AssertionError("live eHD summon identity/reference was lost");
    byte[] unknownIdentityPacket = Files.readAllBytes(Path.of(args[0]));
    java.nio.ByteBuffer.wrap(unknownIdentityPacket).putLong(4, 902L);
    cuU unknown = new cuU();
    unknown.dp(unknownIdentityPacket);
    consumer.b(unknown);
    if (summon.c(ffw.sgC) != 17 || summon.c(ffw.sgD) != 4)
      throw new AssertionError("unregistered positive UID changed the registered summon");
    System.out.println("PASS actual cuU12873 -> cjU.b -> registered live bje/eHD UID901 applied eHj body; unregistered UID902 ignored");
  }
}

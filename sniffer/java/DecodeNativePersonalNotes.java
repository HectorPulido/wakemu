import java.nio.file.Files;
import java.nio.file.Path;

/** Reads a local notes file using the installed client's original note decoder. */
public final class DecodeNativePersonalNotes {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("Usage: DecodeNativePersonalNotes notes.dat");
        aoG input = aoG.dx(Files.readAllBytes(Path.of(args[0])));
        int version = -1;
        if (input.aJp() == -1) version = input.aJp(); else input.tv(0);
        int count = input.aJp();
        System.out.println("version=" + version + " count=" + count);
        for (int index = 0; index < count; index++) {
            bUY note = new bUY();
            note.b(input, version);
            int dx = note.getX() + 9, dy = note.getY() + 4;
            System.out.printf("note=%d id=%d x=%d y=%d z=%d icon=%d nativeFlag=%s text=%s dx=%d dy=%d distance=%.3f%n",
                index, note.d(), note.getX(), note.getY(), note.NN(), note.bwX(), note.erZ(), note.hF(), dx, dy, Math.hypot(dx, dy));
        }
    }
}

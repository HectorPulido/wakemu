/** Verify native classes in the actual application loader, never a split runtime package. */
public final class ProbeNativePathClearVerification {
    public static void main(String[] args) throws Exception {
        boolean expectInvalid = args.length == 1 && args[0].equals("--expect-invalid");
        try {
            Class.forName("acS", true, ProbeNativePathClearVerification.class.getClassLoader()).getDeclaredMethods();
            if (expectInvalid) throw new AssertionError("Expected disabled hook to fail JVM verification");
            System.out.println("PASS actual JVM verifies original native acS in its application loader");
        } catch (VerifyError error) {
            if (!expectInvalid || !error.getMessage().contains("acS.bvC") || !error.getMessage().contains("aload_0")) throw error;
            System.out.println("REPRODUCED exact JVM VerifyError in disabled acS.bvC hook; no live client involved");
        }
    }
}

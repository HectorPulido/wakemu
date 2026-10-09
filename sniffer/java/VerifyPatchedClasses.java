public final class VerifyPatchedClasses {
    public static void main(String[] args) throws Exception {
        ClassLoader loader = ClassLoader.getSystemClassLoader();
        Class<?> movement = Class.forName("adf", false, loader);
        Class<?> actor = Class.forName("acX", false, loader);
        System.out.println("VERIFIED " + movement.getDeclaredMethod("b", actor));
        Class<?> shortcut = Class.forName("bPO", false, loader);
        System.out.println("VERIFIED " + shortcut.getDeclaredMethod("eH", String.class));
        System.exit(0);
    }
}

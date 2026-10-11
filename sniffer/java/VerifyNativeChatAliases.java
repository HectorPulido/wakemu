/** Loads the installed native command descriptor through its original SAX parser. */
public final class VerifyNativeChatAliases {
    public static void main(String[] args) throws Exception {
        aSV commands = new aSV();
        if (!commands.g(aNT.czG())) throw new AssertionError("Native descriptor registration failed");
        String[] aliases = {"/b", "/d", "/a", "/admin", "/f"};
        String[] expected = {"BattlegroundMessageCommand", "IntergameMessageCommand",
            "AdminMessageCommand", "AdminMessageCommand", "PoliticMessageCommand"};
        for (int index = 0; index < aliases.length; index++) {
            int matches = 0;
            for (aSX command : commands.getChildren()) {
                if (!command.cVc().matcher(aliases[index]).matches()) continue;
                String actual = command.cUV().getClass().getSimpleName();
                if (!actual.equals(expected[index])) throw new AssertionError("Unexpected alias mapping: " + aliases[index]);
                matches++;
                System.out.println("PASS " + aliases[index] + " -> " + actual + " pattern=" + command.cVc());
            }
            if (matches != 1) throw new AssertionError("Alias must match exactly one installed command: " + aliases[index]);
        }
        System.out.println("PASS original SAX registration; no translated alias substitution or client patches");
        if (args.length != 1) throw new IllegalArgumentException("Usage: VerifyNativeChatAliases worlds.lib-url");
        cdH.bla();
        cdH worlds = cdH.exY();
        worlds.dW(args[0]);
        cdI ordinary = worlds.mN(1134);
        if (ordinary == null || ordinary.eyc()) throw new AssertionError("World1134 must be ordinary in installed catalog");
        int battlegrounds = 0;
        long sample = -1;
        for (long identity : worlds.eyb().keys()) {
            if (worlds.mN(identity).eyc()) {
                battlegrounds++;
                sample = identity;
            }
        }
        if (battlegrounds == 0) throw new AssertionError("Installed catalog must contain a real battleground world");
        System.out.println("PASS original world catalog: worlds=" + worlds.eyb().size()
                + " world1134.battleground=false battlegrounds=" + battlegrounds
                + " sample=" + sample);
        System.out.println("LIMIT command outbound suppression is established by bytecode; full actor command execution is not tested here");
    }
}

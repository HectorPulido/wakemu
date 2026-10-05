import io.netty.channel.embedded.EmbeddedChannel;
import io.netty.channel.DefaultChannelId;
/** Run with CaptureAgent; no game connection, credentials, or graphics. */
public final class ProbeCaptureCloseLifecycle {
    public static void main(String[] args) {
        EmbeddedChannel pipeline = new EmbeddedChannel(DefaultChannelId.newInstance());
        pipeline.close().syncUninterruptibly();
        if (pipeline.isOpen()) throw new AssertionError("close changed behavior");
        EmbeddedChannel direct = new EmbeddedChannel(DefaultChannelId.newInstance());
        direct.unsafe().close(direct.newPromise());
        if (direct.isOpen()) throw new AssertionError("unsafe close changed behavior");
        System.out.println("PASS: pipeline and direct unsafe close preserve behavior");
        System.exit(0);
    }
}

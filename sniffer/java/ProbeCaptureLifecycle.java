import io.netty.channel.embedded.EmbeddedChannel;
import io.netty.channel.ChannelInboundHandlerAdapter;
public class ProbeCaptureLifecycle {
 public static void main(String[] args) {
  EmbeddedChannel channel = new EmbeddedChannel(new ChannelInboundHandlerAdapter());
  channel.pipeline().fireExceptionCaught(new IllegalStateException("SECRET_SENTINEL"));
  channel.close().syncUninterruptibly();
  System.exit(0);
 }
}

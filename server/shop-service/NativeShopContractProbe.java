import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import com.ankama.shopi.client.model.*;

/** Exercise the installed client's actual adapters using public pilot fixtures. */
public final class NativeShopContractProbe {
    public static void main(String[] args) throws Exception {
        Path fixtures = Path.of(args[0]);
        foA.a(new bGt());
        Article article = Article.fromJson(Files.readString(fixtures.resolve("Article.json")));
        CreateCartRequest cartRequest = new CreateCartRequest().addCartDetailsItem(
            new CartDetailRequestOneOf().discriminator(CartDetailRequestOneOf.DiscriminatorEnum.CARTDETAILCLASSICREQUEST)
                .cartDetailClassicRequest(new CartDetailClassicRequest().articleId(article.getId()).quantity(1)
                    .chosenReferences(article.getSingleReferences().stream().map(cca::b)
                        .filter(java.util.Objects::nonNull).toList())));
        Files.writeString(fixtures.resolve("NativeCreateCartRequest.json"), cartRequest.toJson());
        if (cca.a(article) == null) throw new AssertionError("Native article rejected");
        Category category = Category.fromJson(Files.readString(fixtures.resolve("Category.json")));
        if (cca.av(List.of(category)).size() != 1) throw new AssertionError("Category rejected");
        CartPaymentModeList modes = CartPaymentModeList.fromJson(Files.readString(fixtures.resolve("CartPaymentModeList.json")));
        PaymentRequestOneOf payment = cca.a(modes);
        if (payment == null || payment.getVirtualPaymentRequest().getPaymentModeId() != VirtualPaymentModeId.OG
                || !"OGR".equals(payment.getVirtualPaymentRequest().getCurrency())) {
            throw new AssertionError("Native OG payment rejected");
        }
        PromoteGroup home = PromoteGroup.fromJson(Files.readString(fixtures.resolve("PromoteGroup.json")));
        if (cca.a(home) == null) throw new AssertionError("Native home rejected");
        AnkamaOgrinePayment paid = AnkamaOgrinePayment.fromJson(Files.readString(fixtures.resolve("AnkamaOgrinePayment.json")));
        if (paid.getPaymentId() == null || paid.getOrderId() == null) throw new AssertionError("Payment rejected");
        CreateAnkamaOgrinePaymentRequest request = new CreateAnkamaOgrinePaymentRequest().orderId(paid.getOrderId());
        if (!request.toJson().contains("order_id")) throw new AssertionError("Payment request contract changed");
        for (String model : new String[]{"CatalogPage", "PromoteGroup", "Cart", "Order"}) {
            Class<?> type = Class.forName("com.ankama.shopi.client.model." + model);
            type.getMethod("fromJson", String.class).invoke(null, Files.readString(fixtures.resolve(model + ".json")));
        }
        System.out.println("Native shop article, category, OG payment and DTO contracts: OK");
        System.exit(0); // Native client executors otherwise keep this standalone probe alive.
    }
}

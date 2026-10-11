# Final sign-off: enchantment and recycling economy

Final `prices.csv` SHA-256: `d8acd33cfd41501b0e7caf02930f9c5c9d0a6cf1b3ac67a2381b44ece35dfba7`.

The final catalog was re-read after all coordinated manual overrides and recursive ingredient repricing. No price, policy, service, or database changes were made in this sign-off.

- Reviewed 794 enchantment/sublimation references: all 464 sublimations remain present; all 253 legacy type 626 runes retain publication holds.
- Recomputed 13,193 recycling conversions using final source/product prices, native float32 factors, and the template unidentified bonus. **0 template-unbound conversions have expected output replacement value above source price.** The final audit replaces `recycling-value-audit.csv` and explicitly labels every row `final`.
- Modern shard 27083 and powder 27093 remain 110 kamas; no missing-source scarcity premium was added.
- The eight reviewed sublimation ceiling discounts retain 5,000,000 kamas and their explicit explanations. Recursive input repricing does not erase the ceiling-versus-cost tradeoff.
- Neopotions 32701/32702 retain their coordinated 5,800-kama exceptions to the bread soft cap. The absolute 10-million maximum remains respected.

Runtime instance binding, sockets, equipped/container state and disabled-reference settings can restrict recycling further. This audit intentionally checks the permissive unbound native-template case; it does not assume every owned item can recycle. Fractional outcomes remain stochastic and aggregate before rounding, so expected conversion value is the appropriate bulk procurement check.

## Final individually annotated sublimation ceilings

| Ref | Name | Final price | Final modeled ingredient cost |
|---|---|---:|---:|
| 24131 | Constancia | 5,000,000 | 6,037,000 |
| 24137 | Confianza | 5,000,000 | 13,826,000 |
| 25797 | Fuerza Hercúlea | 5,000,000 | 24,438,000 |
| 25798 | Alternancia II | 5,000,000 | 16,837,000 |
| 25800 | Sangre del Martirio | 5,000,000 | 24,438,000 |
| 25802 | Aura de Llamas | 5,000,000 | 20,040,000 |
| 27187 | Manejo: Daga | 5,000,000 | 9,640,000 |
| 27188 | Manejo: Escudo | 5,000,000 | 16,837,000 |

Verdict: final pricing and recycling consistency approved within the documented modeled-cost uncertainty and deliberate ceiling discounts. No critical pricing inconsistency found.

## Narrow final delta attestation

Final catalog SHA-256: `ad7d7d30297d5fae083b81dfb0249667280cb630aa56818c93603507240c8d44`. The sole subsequent pricing correction is equipment 24103 (Dora N.I.O.) from 5,000,000 to 5,100,000 kamas; root confirmed all other rows unchanged. The recycling audit source price for this reference was refreshed where present (1 row). Raising a source price cannot create an expected recycling-value deficit. No enchantment/sublimation price changed, and the previous sign-off remains valid.

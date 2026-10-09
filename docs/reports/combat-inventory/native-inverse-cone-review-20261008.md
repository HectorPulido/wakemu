# Shared inverse-cone geometry

Actual morph933 run04 commits parent8587 and independent child8588/8589, restores the base book and rejects expired raw UID. Child8590 alone fails at effect416849/family865 because generic geometry lacks anC `cone_inv-3`.

Original anC.p enumerates rows0..<height, each y=-row..row, with X=height-1-row. Nonpositive heights produce an empty list; bEj is false. anC inherits anc orientation/membership without an override, so the existing audited forward/transpose transforms and signed-byte physical-radius handling apply. The shared `native_area_shape` now implements that contract for every inverse cone, without a spell/effect reference patch.

Two pure regressions pass: exact native ordered height3 points/nonpositive boundary and orientation/radius membership. Original `ProbeNativeInverseConeAreas.java` is queued for differential orientation/radius export before the next actual933 replay. No services or runtime HP/state injection occurred.

Original Java differential completed:108 rows,540 assertion groups covering ordered shapes/cells, membership and physical radii1/2 match Python exactly. Fixture `.runtime/combat-review-20261008/morph933-casting-roots/native-inverse-cone-oracle.json` SHA256 `ac25b8e4495ba44291249ebb74d80bc9c493658781dd73e175e34ba5745b6c08`; frozen snapshot manifest SHA256 `c8bcfd207c07ffbd631ffc756ab4ca192732d5075159dc8b318febd62d43b1b7`.

Original command (executed by Luna, not a service):

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local sniffer/java/ProbeNativeOrientedAreas.java sniffer/java/ProbeNativeInverseConeAreas.java
java -Xmx128m -cp '.runtime/local:client/lib/*' ProbeNativeInverseConeAreas .runtime/combat-review-20261008/morph933-casting-roots/native-inverse-cone-oracle.json
```

This closes the sampled shared geometry contract; actual three-child morph lifecycle replay05 now completes with all three independent children, restoration and foreign/expired UID rejection. See `native-morph933-lifecycle-review-20261008.md` for source-bound evidence and limits.

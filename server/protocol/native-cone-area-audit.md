# Native anv cone geometry

Java22 javap -c -p anv proves that p(int[]) requires exactly one int32 height.
It generates ordered raw points (x,y): x=0..<height and y=-x..x. Thus cone-2
is [(0,0),(1,-1),(1,0),(1,1)], not a cone of length2 beyond its tip. Height0
and negative heights produce empty lists. bEm's native concat recipe is
«cone-<height>»; bEj=false and bEk=and.cJa use the same directional anc/amX
transforms already audited for anI/anE/anJ. Actor membership and enumerated
cells retain the native difference for coincident diagonal facing.

combat_area_geometry.native_area_shape handles classanv with the exact
native serialized height. The common target selector, retained group cells
and relative-group candidate authority already call these geometry helpers;
no breed/spell branch or separate cone targeting approximation is introduced.
This parametric shape needs no opaque native_area_points metadata export.

ProbeNativeConeAreas exports native-cone-area-fixture.json:108 cases covering
heights-1/0/1/2/3/4, cardinal/diagonal/skew orientation and all8 fallback
facings when origin/reference coincide. Each records native cell enumeration,
actor membership and physical radius1/2 expansions. Three dedicated tests
compare full ordered cell output and every point in a13x13 membership grid,
plus actual fcE actor selection and group-cell routing with differing Z.
Nine cone/existing directional tests passed. No large active audit was run
while equipment export was in progress;6469 end-to-end re-audit is pending.

Reproduce: javac -proc:none -classpath 'client/lib/*:.runtime/java' -d
.runtime/java sniffer/java/ProbeNativeConeAreas.java
sniffer/java/ProbeNativeOrientedAreas.java; Java22 classpath same,
ProbeNativeConeAreas server/protocol/native-cone-area-fixture.json.

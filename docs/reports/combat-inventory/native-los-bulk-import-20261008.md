# Bulk native LOS topology import

The live client on map1086 rejected ranged spells because native topology columns were exported only for map1134. The original exporter now supports all installed map archives in a single process. Imported 934 maps out of 961 installed topology archives; 27 archives still fail decoding and are listed in the accompanying JSON. No invented clear rays are used.

All exported topology files were copied into the existing world container without restarting the ongoing fight. Build combat-20261008-r03 also includes the files for durable deployment; it is built but not yet activated. Map1086 contains26244 original columns. A live-container static ray call loads that file and returns clear for the nearby test ray. Actual client cast acceptance remains pending.

Regenerate missing maps:

```sh
javac -proc:none -cp "client/lib/*" -d /tmp/wakemu-los-export sniffer/java/ExportNativeLOSTopology.java
java -Xmx512m -cp "/tmp/wakemu-los-export:client/lib/*" ExportNativeLOSTopology --all server/protocol/native-los-topology
```

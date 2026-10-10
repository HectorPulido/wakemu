# Native dimensional-rift interaction protocol — 2026-10-09

Offline evidence from the installed client; no service restart, deployment, database write or gameplay change. The extractor and native decoder assertions are reproducible below. Numeric references are version-specific client data, not invented server policy.

## Portal entry

`bCy` is the `InfiniteWaveEntrance` implementation produced by `bCz`. Its `dSG()` parses the object's `bbz` parameter as a decimal wave-definition ID and resolves it with `byX.GA(id)`. This closes the earlier provisional decimal-suffix evidence. Both `dSu()` and `dSD()` select `QT.bjE`, whose enum initialization defines `ENTER = 11`.

`bEG.b(QT)` creates `cpF`. Its opcode is **12870**, and its payload is exactly **12 bytes**, big-endian: `i64 object_uid`, `i16 action`, `u16 zero padding`. The wire action at all ten external portals is therefore **11**. Keep object location, ownership/session eligibility and destination validation server-authoritative.

## Interior activators

`bBH` implements `GenericActivableInteractiveElement`. It parses `bbz` into a descriptor reference in table **31**, native record `aLl`, and builds `flb`. `baN` assigns consecutive wire actions across descriptor groups; these are offsets, not raw action IDs such as1835. `flb.dSD()` defaults to0, but that default does not make every activator's action0 a fight-start action.

| Maps | Descriptor | Start action | Other actions | Key cost at start |
| --- | --- | --- | --- | --- |
| 1314,1316,1320,1322,1329,1330,1345 | 1456 | **0** | 1 opens map-specific background/lore | none in descriptor |
| 1318, Frigost ultimate | 1457 | **1** | 0 displays missing-key bubble; 2 lore | **1 ×28789**, consume=true |
| 1324, Zinit ultimate | 1458 | **1** | 0 displays missing-key bubble; 2 lore | **1 ×28790**, consume=true |
| 1347, Shustuft ultimate | 1477 | **1** | 0 displays missing-key bubble; 2 lore | **1 ×29594**, consume=true |

Interior actions use the same12870 objectUID/action layout. Ultimate key fields are `aLo.cod()` reference, `coe()` quantity, `cof()` consumption; `baN` maps these into `fle`. The absent-key scripts have criteria `not IsHero() and GetItemQuantity(reference) <= 0`. Start scripts require `not IsHero()`. Ordinary start script3293 and ultimate start scripts3296,3299,3345 are **not shipped** in `scripts.jar`; client data does not recover their server-side encounter logic.

`aLm.cnZ()=1` maps to `flQ.PLAY_SCRIPT`; `aLm.awM()` supplies the action/script reference. These two fields must not be confused. Ordinary action1 scripts3294,3302,3303,3304,3314,3315,3347 directly call `UI.displayBackground` with386,387,388,389,394,395,411 respectively. Ultimate lore scripts3297,3300,3346 select390,391,410. Missing-key scripts3295,3298,3344 display `infinite.waves.no.key.for.ultimate.rifts`. **Do not start encounters on lore or absent-key actions.**

## New-wave combat notification

S2C **13051**, native decoder `cwF`, is exactly **16 bytes**, four big-endian signed32-bit integers:

| Offset | Field | Native consumer |
| --- | --- | --- |
| 0 | fight_id | `cuQ.fj` / `bhe()` |
| 4 | action_id | `cvB.fl` / `cbc()` |
| 8 | dependency_action_id | `cvB.fl` / `eId()` |
| 12 | wave_count | `cwF.dp` / `TP()` |

`cko` creates `aUXX` with the notification action ID, native sequence category, duration0, current fight context and wave count. `aUXX.cXi()` displays localized `infinite.waves.new.wave.notification` for2000ms. This is a combat sequencing message: use the existing fight/action authority and ensure referenced dependencies are valid. Sending13051 alone neither spawns enemies nor establishes an infinite-wave lifecycle. Native decoder assertions validate the four fields independently using123,456,-1,7.

## Result counters

The root combat-result protobuf `ji` has descriptor full name `FightReport` (confirmed by `ji.Tv().getFullName()`), consumed by `bvS`. It exposes four independently optional `int32` values:

| Protobuf field | UI field | Native accessor |
| --- | --- | --- |
| 10 | waveCount | `TP()` / presence `TO()` |
| 11 | waveMonsterCount | `TR()` / presence `TQ()` |
| 12 | realWaveCount | `TT()` / presence `TS()` |
| 13 | realWaveMonsterCount | `TV()` / presence `TU()` |

`ji.writeTo` directly confirms field numbers10–13 and int32 encoding. `bvS` uses separate localized tooltips for actual completed waves and actual kills. Do not collapse reached/adjusted counters into actual counters without a documented policy. These fields belong to the ROOT FightReport, not individual player/member records. Player field 10 is a separate dead flag and must not be overwritten. This extraction establishes root report fields, not ranking persistence, ranking opcodes, season boundaries or reward formulas.

## Reproduction

```sh
mkdir -p .runtime/local/rift-protocol-review
javac -proc:none -cp 'client/lib/*' -d .runtime/local/rift-protocol-review sniffer/java/ExportRiftInteractionEvidence.java
java -Djava.awt.headless=true -cp '.runtime/local/rift-protocol-review:client/lib/*' ExportRiftInteractionEvidence .runtime/local/rift-protocol-review/interaction.json
javap -p -c -classpath 'client/lib/*' bCy bEG QT bBH baN flb flQ cpF cuQ cvB cwF cko aUXX ji bvS
```

The Java tool exports all four interior descriptors and shipped Lua action text, then asserts portal opcode/action and native13051 decoding. Execution passed. Local output contains no player data or credentials.

## Extracted descriptor evidence

```json
{
  "binary_table": 31,
  "descriptors": [
    {
      "descriptor_id": 1456,
      "groups": [
        {
          "id": 1784,
          "clx": 405,
          "cod": 0,
          "coe": 0,
          "cof": false,
          "cnd": 0,
          "cog": 0,
          "actions": [
            {
              "wire_action": 0,
              "native_id": 1835,
              "criterion": "",
              "raw_cob": 1.0,
              "effects": [
                {
                  "action_reference": 3293,
                  "effect_type": 1,
                  "criterion": "not IsHero()",
                  "parameters": []
                }
              ]
            }
          ]
        },
        {
          "id": 1785,
          "clx": 406,
          "cod": 0,
          "coe": 0,
          "cof": false,
          "cnd": 0,
          "cog": 0,
          "actions": [
            {
              "wire_action": 1,
              "native_id": 1836,
              "criterion": "",
              "raw_cob": 1.0,
              "effects": [
                {
                  "action_reference": 3294,
                  "effect_type": 1,
                  "criterion": "not IsHero() and GetInstanceId() == 1314",
                  "parameters": [
                    "false"
                  ]
                },
                {
                  "action_reference": 3302,
                  "effect_type": 1,
                  "criterion": "not IsHero() and GetInstanceId() == 1316",
                  "parameters": [
                    "false"
                  ]
                },
                {
                  "action_reference": 3303,
                  "effect_type": 1,
                  "criterion": "not IsHero() and GetInstanceId() == 1320",
                  "parameters": [
                    "false"
                  ]
                },
                {
                  "action_reference": 3304,
                  "effect_type": 1,
                  "criterion": "not IsHero() and GetInstanceId() == 1322",
                  "parameters": [
                    "false"
                  ]
                },
                {
                  "action_reference": 3314,
                  "effect_type": 1,
                  "criterion": "not IsHero() and GetInstanceId() == 1329",
                  "parameters": [
                    "false"
                  ]
                },
                {
                  "action_reference": 3315,
                  "effect_type": 1,
                  "criterion": "not IsHero() and GetInstanceId() == 1330",
                  "parameters": [
                    "false"
                  ]
                },
                {
                  "action_reference": 3347,
                  "effect_type": 1,
                  "criterion": "not IsHero() and GetInstanceId() == 1345",
                  "parameters": [
                    "false"
                  ]
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "descriptor_id": 1457,
      "groups": [
        {
          "id": 1786,
          "clx": 408,
          "cod": 0,
          "coe": 0,
          "cof": false,
          "cnd": 0,
          "cog": 0,
          "actions": [
            {
              "wire_action": 0,
              "native_id": 1837,
              "criterion": "not IsHero()",
              "raw_cob": 1.0,
              "effects": [
                {
                  "action_reference": 3295,
                  "effect_type": 1,
                  "criterion": "not IsHero()\r\nand GetItemQuantity(28789) <= 0",
                  "parameters": [
                    "false"
                  ]
                }
              ]
            }
          ]
        },
        {
          "id": 1787,
          "clx": 407,
          "cod": 28789,
          "coe": 1,
          "cof": true,
          "cnd": 0,
          "cog": 0,
          "actions": [
            {
              "wire_action": 1,
              "native_id": 1838,
              "criterion": "not IsHero()",
              "raw_cob": 1.0,
              "effects": [
                {
                  "action_reference": 3296,
                  "effect_type": 1,
                  "criterion": "not IsHero()",
                  "parameters": []
                }
              ]
            }
          ]
        },
        {
          "id": 1788,
          "clx": 406,
          "cod": 0,
          "coe": 0,
          "cof": false,
          "cnd": 0,
          "cog": 0,
          "actions": [
            {
              "wire_action": 2,
              "native_id": 1839,
              "criterion": "",
              "raw_cob": 1.0,
              "effects": [
                {
                  "action_reference": 3297,
                  "effect_type": 1,
                  "criterion": "not IsHero()",
                  "parameters": [
                    "false"
                  ]
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "descriptor_id": 1458,
      "groups": [
        {
          "id": 1789,
          "clx": 408,
          "cod": 0,
          "coe": 0,
          "cof": false,
          "cnd": 0,
          "cog": 0,
          "actions": [
            {
              "wire_action": 0,
              "native_id": 1840,
              "criterion": "",
              "raw_cob": 1.0,
              "effects": [
                {
                  "action_reference": 3298,
                  "effect_type": 1,
                  "criterion": "not IsHero()\r\nand GetItemQuantity(28790) <= 0",
                  "parameters": [
                    "false"
                  ]
                }
              ]
            }
          ]
        },
        {
          "id": 1790,
          "clx": 407,
          "cod": 28790,
          "coe": 1,
          "cof": true,
          "cnd": 0,
          "cog": 0,
          "actions": [
            {
              "wire_action": 1,
              "native_id": 1841,
              "criterion": "",
              "raw_cob": 1.0,
              "effects": [
                {
                  "action_reference": 3299,
                  "effect_type": 1,
                  "criterion": "not IsHero()",
                  "parameters": []
                }
              ]
            }
          ]
        },
        {
          "id": 1791,
          "clx": 406,
          "cod": 0,
          "coe": 0,
          "cof": false,
          "cnd": 0,
          "cog": 0,
          "actions": [
            {
              "wire_action": 2,
              "native_id": 1842,
              "criterion": "",
              "raw_cob": 1.0,
              "effects": [
                {
                  "action_reference": 3300,
                  "effect_type": 1,
                  "criterion": "not IsHero() ",
                  "parameters": [
                    "false"
                  ]
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "descriptor_id": 1477,
      "groups": [
        {
          "id": 1827,
          "clx": 408,
          "cod": 0,
          "coe": 0,
          "cof": false,
          "cnd": 0,
          "cog": 0,
          "actions": [
            {
              "wire_action": 0,
              "native_id": 1878,
              "criterion": "",
              "raw_cob": 1.0,
              "effects": [
                {
                  "action_reference": 3344,
                  "effect_type": 1,
                  "criterion": "not IsHero()\r\nand GetItemQuantity(29594) <= 0",
                  "parameters": [
                    "false"
                  ]
                }
              ]
            }
          ]
        },
        {
          "id": 1828,
          "clx": 407,
          "cod": 29594,
          "coe": 1,
          "cof": true,
          "cnd": 0,
          "cog": 0,
          "actions": [
            {
              "wire_action": 1,
              "native_id": 1879,
              "criterion": "",
              "raw_cob": 1.0,
              "effects": [
                {
                  "action_reference": 3345,
                  "effect_type": 1,
                  "criterion": "not IsHero()",
                  "parameters": []
                }
              ]
            }
          ]
        },
        {
          "id": 1829,
          "clx": 406,
          "cod": 0,
          "coe": 0,
          "cof": false,
          "cnd": 0,
          "cog": 0,
          "actions": [
            {
              "wire_action": 2,
              "native_id": 1880,
              "criterion": "",
              "raw_cob": 1.0,
              "effects": [
                {
                  "action_reference": 3346,
                  "effect_type": 1,
                  "criterion": "not IsHero() ",
                  "parameters": [
                    "false"
                  ]
                }
              ]
            }
          ]
        }
      ]
    }
  ],
  "native_wave_notification_assertion": "PASS",
  "native_portal_action_assertion": "PASS",
  "installed_lua_scripts": {
    "genericIEActions/3293.lua": "NOT_SHIPPED",
    "genericIEActions/3294.lua": "-- Action Id : 3294\n-- Action Type : 1\n\nUI.displayBackground(386)\n",
    "genericIEActions/3295.lua": "-- Action Id : 3295\n-- Action Type : 1\n\nBubbleText.closeBubbleAttachedTo(userId)\r\n\r\nlocal bubbleId = BubbleText.prepareWakfuBubble(userId, 0, 60, false)\r\nBubbleText.setText(bubbleId, \"infinite.waves.no.key.for.ultimate.rifts\")\r\nBubbleText.attachToMobile(bubbleId, userId)\r\nBubbleText.show(bubbleId)\n",
    "genericIEActions/3296.lua": "NOT_SHIPPED",
    "genericIEActions/3297.lua": "-- Action Id : 3297\n-- Action Type : 1\n\nUI.displayBackground(390)\n",
    "genericIEActions/3298.lua": "-- Action Id : 3298\n-- Action Type : 1\n\nBubbleText.closeBubbleAttachedTo(userId)\r\n\r\nlocal bubbleId = BubbleText.prepareWakfuBubble(userId, 0, 60, false)\r\nBubbleText.setText(bubbleId, \"infinite.waves.no.key.for.ultimate.rifts\")\r\nBubbleText.attachToMobile(bubbleId, userId)\r\nBubbleText.show(bubbleId)\n",
    "genericIEActions/3299.lua": "NOT_SHIPPED",
    "genericIEActions/3300.lua": "-- Action Id : 3300\n-- Action Type : 1\n\nUI.displayBackground(391)\n",
    "genericIEActions/3302.lua": "-- Action Id : 3302\n-- Action Type : 1\n\nUI.displayBackground(387)\n",
    "genericIEActions/3303.lua": "-- Action Id : 3303\n-- Action Type : 1\n\nUI.displayBackground(388)\n",
    "genericIEActions/3304.lua": "-- Action Id : 3304\n-- Action Type : 1\n\nUI.displayBackground(389)\n",
    "genericIEActions/3314.lua": "-- Action Id : 3314\n-- Action Type : 1\n\nUI.displayBackground(394)\n",
    "genericIEActions/3315.lua": "-- Action Id : 3315\n-- Action Type : 1\n\nUI.displayBackground(395)\n",
    "genericIEActions/3344.lua": "-- Action Id : 3344\n-- Action Type : 1\n\nBubbleText.closeBubbleAttachedTo(userId)\r\n\r\nlocal bubbleId = BubbleText.prepareWakfuBubble(userId, 0, 60, false)\r\nBubbleText.setText(bubbleId, \"infinite.waves.no.key.for.ultimate.rifts\")\r\nBubbleText.attachToMobile(bubbleId, userId)\r\nBubbleText.show(bubbleId)\n",
    "genericIEActions/3345.lua": "NOT_SHIPPED",
    "genericIEActions/3346.lua": "-- Action Id : 3346\n-- Action Type : 1\n\nUI.displayBackground(410)\n",
    "genericIEActions/3347.lua": "-- Action Id : 3347\n-- Action Type : 1\n\nUI.displayBackground(411)\n"
  }
}
```

Serialization correction verified directly: `cpF.aWH` allocates 12 bytes, writes the eight-byte object UID and two-byte action, leaving two zero bytes. The strengthened Java oracle checks the full 12-byte body suffix of the framed native message, not just its opcode. Reject malformed nonzero padding.

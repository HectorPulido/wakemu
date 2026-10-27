-- User-requested Rift variety; original native species and source facts remain intact.
-- Ordinary additions share an existing Rift family, have no special world role,
-- and never spawn below the original pool's minimum level.
-- Milestones contain activated native dominants (property115).
-- Dungeon bosses require a separate paid-combat qualification before admission.
-- Existing admissions retain their frozen catalogs and policies.
WITH additions AS (
    SELECT $rift_variety${"3":{"additional_species_refs":[4078],"milestone_species_refs":[4085,4092,4094]},"4":{"additional_species_refs":[1153,4760],"milestone_species_refs":[2132,4256,4753,4764,5108]},"5":{"additional_species_refs":[2074,2075,2076,2078,2083,2084,2339,2340,2341,2342,2364,2365,2366,2367,2967,2968,2969,2970,2971,4228,4229,4230,4716,4717,4718,4719],"milestone_species_refs":[2123,2125,2134,2983,4236,4382,4500,5008]},"6":{"additional_species_refs":[2988,3077,3091],"milestone_species_refs":[2121,4373,4374,4375,5038]},"7":{"additional_species_refs":[],"milestone_species_refs":[2127,4351,4352,4354,4355]},"8":{"additional_species_refs":[5053,5054,5055,5056,5134,5135,5136,5173,5174,5175,5179,5180,5181,5185,5186,5187,5244,5245,5246],"milestone_species_refs":[4328,4351,4353,5057,5132,5138,5177,5183,5189,5248]},"19":{"additional_species_refs":[1168,2074,2075,2084,2346,2352,4726],"milestone_species_refs":[2114,2134,4384,5008]},"20":{"additional_species_refs":[],"milestone_species_refs":[4218,4331,5171,5177,5189]},"25":{"additional_species_refs":[],"milestone_species_refs":[4328,5057,5183,5236,5278,5284,5290,5296,5302]},"37":{"additional_species_refs":[5167,5168,5169,5238,5239,5240,5274,5275,5276,5280,5281,5282,5286,5287,5288,5292,5293,5294,5298,5299,5300],"milestone_species_refs":[4218,4331,5171,5242,5278,5284,5290,5296,5302]}}$rift_variety$::jsonb AS value
)
UPDATE settings AS setting
SET value = (
    SELECT jsonb_object_agg(entry.key, entry.value || COALESCE(additions.value->entry.key, '{}'::jsonb))
    FROM jsonb_each(setting.value) AS entry
)
FROM additions
WHERE setting.name = 'rift_catalog';

# API Basics

Universal Tau Tracker tends to communicate with JSON messages.

## Write Operations

All write operations are `POST` requests.

They all require a `token` and a `script_version` entry in the top-level JSON object

### Adding Items

URL: `v1/item/add`

Example payload:

    {
        "token": "XXXX",
        "script_version": "1.9",
        "slug": "freebooters-can-opener",
        "name": "Freebooter's Can Opener",
        "mass_kg": 1.48,
        "rarity": "Common",
        "type": "Weapon",
        "tier": 3,
        "description": "A mass produced combat axe. Freebooters often joke that they use it to crack open victims space suits while pillaging. At least, they seem to be laughing when they say it...",

        "accuracy": 0.3,
        "hand_to_hand": true,
        "range": "Short",
        "weapon_type": "Blade",
        "piercing_damage": 9.5,
        "impact_damage": 4.73,
        "energy_damage": 0,
    }


The first part is the same among all item types, the second half (starting from `accuracy`)
is **weapon** specific.

For **armors**, these fields should be added:

    "piercing_defense": 5.13,
    "impact_defense": 14.17,
    "energy_defense": 13.43,

For **medical**, add these fields:

    "strength_boost": 0,
    "agility_boost": 8.25,
    "stamina_boost": 0,
    "intelligence_boost": 0,
    "social_boost": 0,
    "base_toxicity": 10,

**Food** needs these extra fields:

    "target_genotype": "Colonist",
    "affected_stat": "Strength",
    "effect_size": "large",
    "duration_segments": 1,

### Recording Ship Positions

URL: `v1/ship/add`

This endpoint allows you to record all ships that are currently shown at a station.

Example payload:

    {
        "station": "Yards of Gadani",
        "system": "Alpha Centauri",
        "token": "xxxx",
        "script_version": "1.9",
        "ships": [
          {
            "name": "🌍🌎🌏",
            "captain": "KMK",
            "registration": "000-AA014",
            "class": "Private Shuttle"
          },
          {
            "name": "Bebop Alpha",
            "captain": "AndreaEntangle",
            "registration": "003-AA062",
            "class": "Razorback"
          },
          {
            "name": "Camanche Arrow",
            "captain": "soci",
            "registration": "003-AA033",
            "class": "Private Shuttle"
          }
        ]
    }

## Read Operations

### Listing Items

URL: `v1/item/list.json`

Get a list of all items as JSON.

TBD: this might need some adapting when more items are known.

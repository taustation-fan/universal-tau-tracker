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

        "accuracy": 0.3,
        "hand_to_hand": true,
        "long_range": false,
        "weapon_type": "Blade",
        "piercing_damage": 9.5,
        "impact_damage": 4.73,
        "energy_damage": 0,
    }


The first part is the same among all item types, the second half (starting from `accuracy`)
is weapon specific.

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

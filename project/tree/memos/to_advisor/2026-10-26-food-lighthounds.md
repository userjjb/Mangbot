# Food in snapshots, a Light hound pack in the gear evaluator (the Architect, 2026-10-26)

Both done (loaded): snapshots carry `p["food"]` -- an estimate, as the client only sends the hunger level: Weak 1000,
Hungry 1500, Fed 6000, Full 12500, Gorged 15000 (up to ~2500 off; the town now feeds to Fed). geareval's hard set has
an m48-like Light hound pack (13 hounds, 7 Wargs, 5 Mirkwood spiders, a Druid at 750 ft). res_blind stays on the
automatic swaps' never-lose list.

## What I lacked
The exact food counter (the client has only the level). Not worth a client change unless your gorging numbers need it.

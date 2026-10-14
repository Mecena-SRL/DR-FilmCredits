# Formati e destinazioni

I profili sono in `src/drfc/data/destinations.json`. Ogni profilo ha risoluzione, fps, safe area
per lato, scala del testo, velocità consigliata e durata massima.

| Gruppo | Profili | Safe area | Note |
|---|---|---|---|
| Cinema | DCI 2K/4K **Flat** 1.85 (1998×1080 / 3996×2160), **Scope** 2.39 (2048×858 / 4096×1716), Full container | 5% per lato | 24 fps; scala testo 1.0 |
| TV | HD/UHD 25p (EBU R95), 29.97 (SMPTE) | title-safe 5% | scala 1.1, velocità veloce, max ~60 s (le emittenti fissano la durata) |
| Streaming | UHD 23.976, HD | SMPTE: title 90%, action 93% | credito della piattaforma con lo stesso font/dimensione |
| Social verticale | 9:16 1080×1920 (anche 2160×3840) | **asimmetrica**: top 14%, bottom 35%, sinistra 6,5%, destra 17% | evita pulsanti a destra e didascalie in basso; scala 1.35; max 30 s |
| Verticale «pulito» | 9:16 senza interfaccia (Stories, festival verticali) | 8/10/6/6% | |
| Feed | 4:5 1080×1350, 1:1 1080×1080 | 6–10% | |

### Zone UI verticali [Da verificare: le fonti divergono]
- **TikTok** (file In-Feed Ads): top 240 px, bottom 660 px, lati 120 px a 1080×1920; colonna pulsanti
  ~180 px dentro il margine destro a partire da 840 px dall'alto.
- **Instagram Reels** (spec Meta citate): top 14% (~269 px), bottom 35% (672 px), lati 6% (~65 px);
  altre fonti danno valori minori. Il profilo usa i valori **più prudenti** di entrambi.

### Adattamento automatico
- La scala del testo usa il **lato corto** (non l'altezza): in verticale i caratteri non diventano
  enormi.
- Sui formati stretti le sezioni affiancate degradano: 3 gruppi → 2 → coppia ruolo|nome → impilato,
  con avviso.
- La velocità resta in «secondi per attraversare lo schermo», quindi si adatta a ogni altezza.

## Fonti
- [EBU – Safe areas](https://tech-qual.ebu.ch/publications/trev_280-baker) · [Specifiche consegna Europa (R95)](https://help-advancedtv.cape.io/hc/it/articles/4407971511185-Specifiche-Tecniche-Europa)
- [Netflix – Title Safe and Safe Action](https://backlothelp.netflix.com/hc/en-us/articles/4406208331923-Title-Safe-and-Safe-Action-Best-Practices)
- [Socialync – TikTok safe zones](https://www.socialync.io/tools/safe-zones/tiktok) · [Socialync – Reels](https://www.socialync.io/tools/safe-zones/instagram-reels)
- [FirstPier – Instagram safe zones](https://www.firstpier.com/resources/instagram-ad-safe-zones)
- [House of Marketers – Safe zones guide](https://houseofmarketers.com/guide-to-safe-zones-tiktok-facebook-instagram-stories-reels/)

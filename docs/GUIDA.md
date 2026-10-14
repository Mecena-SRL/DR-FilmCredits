# Guida d'uso

## Indice
1. [Installazione](#installazione)
2. [Prima prova in Resolve](#prima-prova-in-resolve)
3. [Il progetto .drfc.json](#il-progetto-drfcjson)
4. [Blocchi e sintassi rapida](#blocchi-e-sintassi-rapida)
5. [Import da CSV / Excel](#import-da-csv--excel)
6. [Stile](#stile)
7. [Tempi: velocità, durata, pause](#tempi-velocità-durata-pause)
8. [Generazione in timeline](#generazione-in-timeline)
10. [Calibrazione e log](#calibrazione-automatica)
11. [Problemi frequenti](#problemi-frequenti)

## Installazione
```
python install/install.py        # oppure doppio clic su install/Installa-Windows.bat / Installa-macOS.command
```
| Cosa | Dove |
|---|---|
| Libreria | Windows `%APPDATA%\DR-FilmCredits\lib` · macOS `~/Library/Application Support/DR-FilmCredits/lib` · Linux `~/.config/DR-FilmCredits/lib` |
| Script di menu | `…/Fusion/Scripts/Utility/DR-FilmCredits.py` |

Impostazioni, calibrazione e ultimo progetto aperto si salvano nella stessa cartella utente.

## I 3 passi del pannello
1. **Cosa crei**: titolo, tipo di opera, destinazione. Con la spunta *Riempi con NOME COGNOME* il progetto
   nasce completo di segnaposto (si vede subito il risultato). *Crea e continua*.
2. **Compila**: elenco unico a sinistra, editor a destra. *Elimina i segnaposto rimasti* toglie ciò che non serve.
3. **Metti in timeline**: un solo pulsante, *Metti in timeline / Aggiorna*. Se cambi qualcosa lo ripremi:
   si aggiornano solo le clip cambiate; i nodi Fusion aggiunti a mano restano.
Le opzioni avanzate sono nella scheda *Aspetto e avanzate*. I Title manuali non si installano più
(`python install/install.py --with-titles` per averli comunque).

## Prima prova in Resolve
1. Apri una timeline di prova e lancia **Workspace › Scripts › Utility › DR-FilmCredits**.
2. Apri `examples/corto_festival_it.drfc.json` (**Apri…**), poi, al passo 3, **Metti in timeline / Aggiorna**.
3. Controlla: durata del clip = durata indicata nell'esito; scorrimento fluido; colonne allineate.
   Per valutare il judder fai un render a piena risoluzione e guardalo in un player.

## Il progetto .drfc.json
Un file JSON leggibile (versionabile con git, modificabile a mano). Percorsi di loghi e media
relativi al file di progetto. Una cartella `fonts/` accanto al progetto viene usata per le misure.

```json
{
  "meta": {"title": "…", "year": 2026, "language": "it", "preset": "it_cinema",
           "copyright_owner": "…", "funding": ["mic_tax_credit"], "ai_used": true, "ai_uses": "montaggio"},
  "format": {"width": 1920, "height": 1080, "fps": 24, "safe_title": 0.9, "background": "transparent"},
  "style": {"theme": "classic", "overrides": {"name": {"family": "Inter", "size": 30}}},
  "timing": {"speed": "normal", "end_mode": "hold_last", "hold_last_s": 4},
  "layout": {"split": "none", "render_mode": "auto"},
  "sequences": [
    {"id": "opening", "kind": "cards", "blocks": [ … ]},
    {"id": "end", "kind": "crawl", "timing": {"fit": "spacing", "target_seconds": 90}, "blocks": [ … ]}
  ]
}
```

## Blocchi e sintassi rapida
Campi comuni: `enabled`, `spacing_before`/`spacing_after` (in righe, vuoto = tema), `hold_s`
(pausa del rullo con il blocco al centro), `page_break` (cartelli), `style` (override locale).

| Tipo | Uso | Sintassi nel riquadro |
|---|---|---|
| `title` | titolo dell'opera | testo |
| `card` | cartello (testa) | `ruolo: Nomi` oppure righe `[card_name] testo` |
| `credit` | credito singolo (impilato o a 2 colonne) | `director: Giulia Ferri` |
| `list` | reparto: 1 colonna, 2 colonne, 2–3 gruppi affiancati, griglie | `ruolo: nome, nome` una riga per ruolo; `---` = nuova colonna |
| `names` | nomi multicolonna (ringraziamenti, comparse) | un nome per riga |
| `cast` | interpreti | `Attore = Personaggio` |
| `music` | brani | paragrafo per brano: `titolo:`, `autori:`, `interpreti:`, `edizioni:`, `accordo:`, `licenziante:`, `agente:`, `cc:`, `team: si`, `extra:` |
| `agreements` | location, noleggi, repertorio, prodotti, opere | `nome \| fornitore \| accordo` |
| `logos` | loghi | `percorso \| tag \| scala \| nome` |
| `media` | foto/video backstage | `percorso \| didascalia \| scala` |
| `legal` | diciture | `@chiave campo=valore` o testo libero (es. `@phonographic owner=Etichetta`) |
| `laurels` | allori festival | (editor dedicato) festival, stato, sezione, anno, premio, oppure PNG ufficiale |
| `text`, `spacer` | testo libero, spazio | testo / numero di righe |

**Ruoli**: si possono usare le chiavi del dizionario (tradotte automaticamente nella lingua delle
diciture: `cinematographer` → «Direttore della fotografia» / «Director of Photography»…) oppure
scrivere il ruolo per esteso. Il menu **Ruoli** inserisce le chiavi.

**Intestazioni**: `dept:camera` (reparto tradotto), `h:thanks` (intestazione standard) o testo libero.

**Disposizione** (`arrangement` dei reparti): `pair` (ruolo | nome), `single` (ruolo sopra nome),
`pairs_2` / `pairs_3` (gruppi affiancati sinistra–centro–destra), `stacked_2..4` (griglia),
`names` (solo nomi). Sui formati stretti degrada da sola (3 → 2 → coppia → impilato) con avviso.

**Loghi dal kit**: nel progetto `{"logo": "mic_dgca"}` al posto del percorso; il file viene preso
dal kit utente nella variante adatta allo sfondo (vedi [logos.md](research/logos.md)).

**Tag dei loghi** usati dai controlli: `mic`, `creative_europe`, `eurimages`, `film_commission`,
`cnc`, `ffa`, `dfff`, `icaa`. Usare PNG con trasparenza (Fusion non legge SVG).

**Accordi**: vedi [music-rights.md](research/music-rights.md) e
[rentals-locations-legal.md](research/rentals-locations-legal.md).

## Import da CSV / Excel
**Crea modello CSV** genera un file con le colonne:
`sezione; sequenza; ruolo; nome; personaggio; titolo; autori; interpreti; editore; accordo; licenziante; fornitore; file; tag; nota`.
- `sezione`: chiave reparto (`camera`, `sound`, …), `cast`, `music`, `locations`, `rentals`,
  `archive`, `products`, `thanks`, `logos`, `media`, `credit`, `legal`. Se vuota si deduce dal ruolo.
- Nomi multipli nella stessa cella: separati da `;` o `|`.
- Separatore `,` `;` o tab rilevato in automatico (Excel italiano usa `;`). `.xlsx` richiede `openpyxl`.
- Le voci si aggiungono ai blocchi del preset (stesso reparto) e prima di loghi/diciture finali.

## Stile
- **Temi**: Classico cinema (Cormorant Garamond), Moderno (Montserrat), Minimale (Inter),
  Festival (DM Serif Display + Lato), Broadcast TV (Arial, alta leggibilità).
- **Set di font** (sovrascrivono i font del tema): Classico (EB Garamond), Elegante (Cormorant
  Garamond), Moderno (Montserrat), Neutro (Inter), Festival (DM Serif Display + Lato), Videoclip
  (Bebas Neue + Inter), Documentario (IBM Plex), Broadcast (Roboto), Solo sistema (Arial, Georgia).
  I font liberi sono in `fonts/` e l'installer li installa per l'utente.
- **Densità**: compatta / normale / ariosa (spazi tra blocchi, tra righe e sotto le intestazioni).
  **Interlinea**: stretta / normale / larga.
- **Sfondo**: `transparent`, `black`, `white`, `#RRGGBB` oppure un oggetto:
  `{"mode": "gradient", "colors": ["#000", "#223"]}`,
  `{"mode": "media", "path": "sfondo.mov", "dim": 0.5, "blur": 10}`,
  `{"mode": "dim", "opacity": 0.5}` (oscura l'immagine sottostante),
  `{"mode": "panel", "color": "#000", "opacity": 0.85}` (pannello dietro la corsia del testo).
  Su sfondi chiari la palette si inverte da sola (testo scuro, loghi in variante scura).
- **Destinazione** (`format.destination`): imposta risoluzione, fps, safe area anche asimmetrica
  (verticale 9:16 con zone UI di TikTok/Reels), scala del testo e velocità consigliata. Elenco:
  `python -m drfc destinations`.
- Dimensioni in px riferiti a 1080 di altezza: in UHD vengono raddoppiate automaticamente.
- **Personalizza stile**: font, stile, dimensione, colore, maiuscole, spaziatura lettere,
  interlinea per ciascuno stile (titolo, intestazione, ruolo, nome, personaggio, piccolo, legale,
  ruolo/nome dei cartelli).
- **Media a lato**: il testo occupa una corsia (es. 50%) e le foto/video con `lane: side`
  scorrono nell'altra, distribuiti lungo tutto il rullo.
- **Nodi Fusion**: *Automatico* (consigliato) = colonne centrate in un Text+ multiriga, colonne
  laterali una riga per Text+ (allineamento perfetto); *Compatto* = meno nodi; *Preciso* = un nodo
  per riga.

## Tempi: velocità, durata, pause
| Opzione | Effetto |
|---|---|
| Lenta / Normale / Veloce | 15 / 11 / 8 s perché una riga attraversi lo schermo, convertiti in px/frame **interi** |
| Personalizzata | px/frame scelti a mano |
| Adatta velocità alla durata | velocità intera più bassa che sta nel tempo; i frame residui allungano la pausa finale → durata esatta |
| Adatta spaziatura alla durata | velocità del preset, spazi tra blocchi allargati/stretti (0,5×–2×) fino alla durata |
| Finale | esce dallo schermo / si ferma sull'ultimo blocco (o sul gruppo loghi + ©) con pausa |
| Pausa su blocco | `hold_s`: il rullo si ferma con quel blocco al centro |
| Cartelli | durata da parole e righe × ritmo (lento ×1,3, veloce ×0,75), min 2,5 s, max 8 s; dissolvenza e nero tra cartelli |

La durata obiettivo si imposta **per sequenza** (testa e coda hanno tempi diversi).

## Generazione in timeline
- **Sezioni**: un clip per rullo; per i cartelli un clip per cartello (default) o uno per sequenza.
  La pagina *Genera* mostra lo stato di ogni sezione: nuova / modificata / invariata / bloccata.
- **Metti in timeline / Aggiorna** (non distruttivo): invariata = intatta; modificata con stessa
  durata = nuovo comp nello stesso clip (proprietà del clip e nodi Fusion aggiunti a mano
  conservati e ricollegati, versione precedente `…_prev`); durata diversa = nuovo clip nella stessa
  posizione/traccia con le stesse proprietà; bloccata = mai toccata. Lo stato è salvato nel
  progetto (`render_state`).
- **Posizione** delle nuove sezioni: testina, inizio o fine timeline (i cartelli mantengono la
  distanza calcolata tra loro; poi si spostano liberamente).
- **Traccia**: traccia dedicata «DR-FilmCredits» (creata se manca) o nuova traccia.
- Il formato (risoluzione, fps) viene preso dalla timeline se è attivo «Usa formato della timeline».
- In Fusion: `DRFC_Scroll` contiene l'unica espressione di scorrimento; i nodi hanno il nome del
  blocco (`end_list_5_T`, `…_M`, `…_L` per i Loader).

## Calibrazione (automatica)
Non va fatta a mano. Alla prima generazione (e a ogni nuova versione di Resolve) il plugin aggiunge
al clip un comp temporaneo con un Text+ di prova, misura la larghezza di 1 e 41 caratteri alla
stessa `Size` (la differenza vale 40 avanzamenti esatti del font, quindi le side-bearing si
cancellano) e ne ricava `em_per_size_width`; poi elimina il comp di prova e salva
`calibration.json`. Se la misura non è possibile si restano sui valori standard, senza errori.
In modalità Avanzata **Ricalibra Text+** cancella il file: la misura si rifà alla generazione
successiva. Valori modificabili a mano: `em_per_size_width`, `anchor_h`, `justify_h`, `baseline_fix_em`.

## Log degli errori
Il pannello scrive `drfc.log` nella cartella utente (vedi README) con errori e avvii. In caso di
errore compare anche una finestra con il testo, invece di sparire.

## Problemi frequenti
| Sintomo | Causa / soluzione |
|---|---|
| Avviso «Font non trovati» | Installare i font del tema o scegliere font installati in *Stile*. |
| Il clip è più corto del rullo | Resolve non ha accettato la durata: il plugin passa da solo alla sequenza di immagini; se l'esito dice di allungare il clip, trascinarne la coda fino alla durata indicata. |
| Loghi non visibili | Percorso errato o SVG: usare PNG; controllare la Verifica. |
| Righe a capo inattese | Ruolo/nome più largo della colonna: ridurre la dimensione o allargare la safe area. |
| Lo scorrimento non parte da 0 | Il comp viene riallineato da solo; se il clip è stato tagliato a mano, rigenerare. |

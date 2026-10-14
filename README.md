# DR-FilmCredits

**Titoli di testa e di coda per DaVinci Resolve Studio: guidati, modulari, a norma, precisi al pixel.**

Si compilano i contenuti (a mano, incollando elenchi o importando un CSV/Excel), si sceglie lo
standard (Italia cinema/TV, USA WGA/DGA, coproduzione europea, streaming, corto/festival,
documentario) e si preme **Genera**: il plugin impagina tutto, calcola velocità e durata, scrive le
diciture legali giuste per ogni accordo e inserisce nella timeline una **composizione Fusion
nativa**, che resta modificabile.

> Supporto: Resolve **Studio 19/20** (Windows, macOS, Linux). Python 3.6+ di sistema, nessuna dipendenza.

## Cosa fa

- **Struttura guidata per standard**: 7 preset con ordine dei blocchi, reparti e controlli
  obbligatori (MiC tax credit e dichiarazione IA, Eurimages, Creative Europe MEDIA, Film Commission,
  WGA/DGA, safe area, durata TV…). Ricerca e fonti in [`docs/research/`](docs/research/README.md).
- **Blocchi modulari**: cartello singolo, credito, reparto a due colonne (ruolo | nome su asse
  centrale), nomi multicolonna, cast (attore | personaggio), brani musicali, location / noleggi /
  repertorio / prodotti, loghi, diciture legali, foto e video di backstage, testo, spazio.
- **Diciture per tipo di accordo** in 5 lingue (it, en, fr, de, es): es. un brano concesso
  gratis diventa «Per gentile concessione di…», uno su licenza «Su licenza di…» (*Courtesy of…*).
- **Loghi bilanciati automaticamente** per peso ottico (un logo largo e uno quadrato risultano
  equivalenti), su righe che vanno a capo da sole.
- **Foto/video di backstage** in riga dentro il rullo oppure in una **corsia laterale** che scorre
  accanto ai crediti.
- **Velocità sempre a pixel interi** (niente judder): lenta / normale / veloce / personalizzata;
  **Adatta a durata** (velocità) o **Adatta spaziatura** (allarga o stringe gli spazi tra i
  blocchi) per arrivare al fotogramma esatto. **Pause** sui blocchi (es. loghi, dedica) e
  finale fermo sull'ultimo blocco.
- **Cartelli** con durata calcolata sulla lettura, dissolvenze, paginazione automatica se un
  elenco non entra, posizioni centro / lower third / upper third.
- **Anteprima nel browser** fedele al frame (stessa funzione di scorrimento), da mandare in
  approvazione.
- **Verifica** prima di generare: crediti e diciture obbligatorie mancanti, loghi richiesti dai
  finanziamenti, accordi musicali incompleti, file mancanti, testo fuori dalla safe area, rullo
  troppo veloce, durata oltre il limite del preset.
- **Pacchetto Title** da trascinare dalla libreria Effetti (cartello, due colonne, lower third,
  brano, copyright) per gli interventi rapidi.

## Installazione

```bash
python install/install.py          # oppure: python3 install/install.py
```
Riavviare Resolve → **Workspace › Scripts › Utility › DR-FilmCredits**.
I Title manuali compaiono in **Effects › Titles › DR-FilmCredits**. Per disinstallare:
`python install/install.py --remove`.

## Uso in 5 passi

1. **Progetto** – scegli il preset, titolo, titolare del ©, lingua delle diciture e i
   finanziamenti (attivano i controlli). Spunta «usata l'IA» se serve la dichiarazione.
2. **Contenuti** – scegli la sequenza (testa/coda), seleziona un blocco e scrivi nel riquadro.
   Sintassi rapida:
   ```
   cinematographer: Luca Marini          ← reparto: ruolo: nomi (chiave o testo libero)
   first_ac: Anna Costa, Ivo Serra
   Marta Lodi = Elena                    ← cast
   titolo: Il mare / autori: A, B / accordo: courtesy / licenziante: Band   ← brano (una riga per campo)
   Villa Rossi | Famiglia Rossi | free   ← location: nome | fornitore | accordo
   loghi/mic.png | mic | 1.0             ← logo: percorso | tag | scala
   @copyright   @ai_disclosure uses=montaggio   ← diciture legali
   ```
   Oppure **Importa CSV/XLSX** (modello generabile dal pulsante, colonne in italiano o inglese).
3. **Stile** – tema (Classico, Moderno, Minimale, Festival, Broadcast), safe area, sfondo,
   corsia media laterale, personalizzazione di ogni stile (font, dimensione, colore, maiuscole,
   spaziatura, interlinea).
4. **Tempi** – velocità, finale, pause, ritmo dei cartelli; per ogni sequenza durata obiettivo e
   modalità di adattamento. «Risultato» mostra subito durata e px/frame.
5. **Verifica e genera** – *Verifica*, *Anteprima nel browser*, **Genera nella timeline**
   (testina / inizio / fine / sostituisci la versione precedente; traccia dedicata), oppure
   *Esporta .comp/.setting*.

Guida completa: [`docs/GUIDA.md`](docs/GUIDA.md).

## Anche da riga di comando (senza Resolve)

```bash
cd src
python -m drfc presets
python -m drfc new it_cinema ../mio_film.drfc.json --title "Il mio film"
python -m drfc template ../crediti.csv && python -m drfc import ../mio_film.drfc.json ../crediti.csv
python -m drfc check ../mio_film.drfc.json
python -m drfc preview ../mio_film.drfc.json
python -m drfc build ../mio_film.drfc.json ../out/      # .comp + .setting + anteprima
```
Esempi pronti in [`examples/`](examples/).

## Architettura

```
src/drfc/
  model.py         progetto .drfc.json, tipi di blocco, default
  presets.py       preset per standard (data/presets/*.json)
  i18n.py          ruoli/reparti (data/roles.json), diciture (data/phrases/*.json), UI (data/ui/*.json)
  phrases.py       diciture per tipo di accordo
  fontmetrics.py   parser TrueType/OpenType: larghezze e interlinea reali dei font installati
  layout.py        impaginazione (colonne, griglie, loghi, media, paginazione cartelli)
  timing.py        velocità intere, adatta-a-durata, spaziatura elastica, pause, cartelli
  validate.py      obblighi da preset/finanziamenti + controlli di qualità
  fusion_writer.py composizione Fusion (.comp / .setting) con scorrimento a espressione unica
  preview.py       anteprima HTML animata
  resolve_bridge.py inserimento in timeline (durata esatta, offset, aggiornamento, fallback)
  ui_wizard.py     pannello guidato UIManager (5 lingue)
  blocktext.py     sintassi rapida dei blocchi · io_import.py CSV/XLSX · templates.py Title manuali
  calibration.py   calibrazione di Text+ dentro Resolve
```

Test: `python -m pytest tests` (motore, writer, diciture, preset, import, e wizard/bridge con
un Resolve simulato).

## Limiti noti

- L'inserimento automatico è stato verificato contro un Resolve **simulato**: alla prima prova
  su Resolve reale eseguire **Calibra Text+** e controllare un rullo breve (vedi
  [`docs/GUIDA.md`](docs/GUIDA.md#prima-prova-in-resolve)).
- Le misure dei testi usano i file dei font installati; se un font manca, le larghezze sono
  stimate e il validatore lo segnala.
- Le diciture legali sono modelli: la formula vincolante è sempre quella del proprio contratto o bando.

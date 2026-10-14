# DR-FilmCredits

**Titoli di testa e di coda per DaVinci Resolve Studio.** Il pannello è guidato, a norma
(Italia, Europa, USA, TV, festival, social) e scrive il risultato direttamente in timeline come
clip Fusion modificabili, con allineamenti calcolati al pixel.

Scegli che cosa stai facendo (corto, lungo, documentario, videoclip, serie, spot, social) e che
cosa hai (cast, troupe, musiche, location, finanziatori, festival…). Compili con i menu a tendina e
premi **Aggiorna**. Il plugin impagina, calcola velocità e durata, scrive le diciture legali
corrette per ogni accordo e mette le clip in timeline. Se poi cambi un nome, si aggiorna **solo**
quella sezione: il resto del lavoro in timeline non viene toccato.

> Richiede **DaVinci Resolve Studio 19 o 20** (Windows, macOS, Linux) e **Python 3** installato
> (lo stesso che Resolve usa per gli script).

---

## Installazione (5 minuti)

### 1. Scarica
- Dalla pagina GitHub del progetto: pulsante verde **Code › Download ZIP**, poi estrai la cartella.
- Oppure chiedi a Ivan lo ZIP già pronto (`DR-FilmCredits-v0.3.0.zip`).
- Il repository è privato? Ivan deve aggiungerti come collaboratrice (GitHub › Settings ›
  Collaborators) e poi puoi scaricarlo.

### 2. Controlla Python
Resolve usa il Python di sistema per gli script.
- **macOS**: in genere è già presente. Se manca, installa Python 3 da python.org.
- **Windows**: installa Python 3 da python.org e spunta **«Add python.exe to PATH»**.

### 3. Installa
- **Windows**: doppio clic su `install/Installa-Windows.bat`
- **macOS**: doppio clic su `install/Installa-macOS.command` (la prima volta: tasto destro › Apri)
- Da terminale (tutti i sistemi): `python3 install/install.py`

L'installer:
- copia il plugin nella cartella utente;
- aggiunge la voce di menu in Resolve;
- installa i **Title** da trascinare;
- installa i **font gratuiti** dei set predefiniti, solo per il tuo utente e senza permessi di amministratore.

### 4. Avvia
Riavvia Resolve e apri una timeline: **Workspace › Scripts › Utility › DR-FilmCredits**.

Non serve altro: la **calibrazione dei caratteri** (come Resolve disegna Text+) si fa da sola alla
prima generazione, e di nuovo quando cambia la versione di Resolve.

Per disinstallare: `python3 install/install.py --remove`. Per aggiornare il plugin: scarica la
nuova versione e rilancia l'installer (i tuoi progetti non vengono toccati).

---

## Uso rapido: 3 passi

**Come funziona, in una riga:** compili il pannello › premi **Metti in timeline** › se cambi
qualcosa premi di nuovo lo stesso pulsante. Si aggiornano solo le clip cambiate, e quello che hai
fatto a mano in timeline resta. Non c'è niente da trascinare dagli Effetti: le clip le crea il plugin.

1. **Cosa crei**
   - Scrivi il titolo, scegli il tipo di opera (corto, lungo, documentario, videoclip…) e dove andrà.
   - Lascia la spunta **Riempi con NOME COGNOME**: il plugin crea *subito tutto* (ruoli, cast,
     musiche, loghi, allori…) con nomi segnaposto, così vedi il risultato e riempi dopo.
   - Spunta solo ciò che c'è davvero (cast, troupe, musiche, location, loghi, festival, ringraziamenti…).
   - **Crea e continua ›**.
2. **Compila**
   - A sinistra c'è l'elenco di tutto. Clicca una voce: a destra scegli il ruolo dal menu (oppure
     scrivi il tuo), metti i nomi separati da virgola e premi **Salva**: passa alla voce successiva.
   - Sezioni a testo (musiche, location, noleggi, cast…): incolli l'elenco e premi **Salva**; la
     dicitura giusta per ogni accordo si scrive da sola (es. gratuito = «Per gentile concessione di…»).
   - **Loghi**: scegli l'ente dal kit (MiC, Film Commission, Europa Creativa…) o aggiungi un tuo PNG.
     **Allori**: festival, stato, sezione, anno.
   - **Su / Giù / Elimina** spostano o tolgono una sezione; **Riordina secondo standard** la mette
     nell'ordine corretto; **Cosa manca?** suggerisce le sezioni tipiche.
   - **Elimina i segnaposto rimasti** toglie tutto ciò che non hai compilato.
3. **Metti in timeline**
   - **Anteprima nel browser** (animata, da mandare in approvazione) e **Verifica**.
   - **Metti in timeline / Aggiorna**: crea le clip la prima volta, poi aggiorna solo quelle cambiate.

**Aspetto e avanzate** (scheda a parte, non serve per iniziare): destinazione, tema, set di font,
densità, interlinea, sfondo, tempi (velocità, durata obiettivo, finale), spaziature per sezione,
blocco delle clip, dichiarazione IA, import CSV.

### Clip in timeline e aggiornamenti
- Ogni **rullo** diventa **una clip**; ogni **cartello** dei titoli di testa diventa una **clip
  separata**, da spostare liberamente sopra le inquadrature.
- Le clip vanno su una traccia dedicata, «DR-FilmCredits».
- **Metti in timeline / Aggiorna** rigenera solo le sezioni cambiate:
  - sezione invariata: non viene toccata;
  - sezione modificata con la stessa durata: nuovo comp **nello stesso clip**. Restano posizione,
    trasformazioni, opacità, colore e i **nodi Fusion aggiunti a mano** (es. un Glow). La
    versione precedente rimane nel clip come `…_prev`;
  - durata cambiata: nuova clip **nella stessa posizione**, con le stesse proprietà;
  - sezione **bloccata**: non viene mai rigenerata.
- Ogni cosa resta modificabile anche a mano nella pagina Fusion: i nodi generati iniziano con
  `DRFC_`, e lo scorrimento è un unico nodo (`DRFC_Scroll`).

---

## Kit loghi (aggiornabile)
Il plugin contiene un registro di **41 enti**:
- MiC/DGCA e Italian Tax Credit;
- tutte le **Film Commission regionali**;
- Rai/Rai Cinema, Cinecittà/Luce, SIAE;
- Europa Creativa MEDIA, emblema UE, Eurimages;
- CNC, FFA, DFFF, ICAA, BFI, UFC, SRG SSR, ÖFI, PGA, American Humane.

Per ciascuno il registro indica:
- la pagina ufficiale;
- se il logo **va richiesto** all'ente (es. MiC tramite DGCA, CNC previa approvazione);
- le regole d'uso essenziali.

I file non sono inclusi perché vanno presi dalla fonte ufficiale nella versione in vigore:
1. nel blocco Loghi scegli l'ente e premi **Pagina ufficiale**, oppure fai la richiesta all'ente;
2. con **Importa file ricevuto…** carichi il PNG o lo ZIP; il plugin estrae i PNG e sceglie da solo
   la variante chiara o scura in base allo sfondo;
3. **Aggiorna kit loghi** scarica i loghi disponibili e l'elenco enti aggiornato dal repository.

Da terminale: `python -m drfc logos list | update | open ID | import ID file | update-registry`.

> Fusion non legge **SVG/PDF**: servono PNG con trasparenza (meglio una versione chiara e una scura).

## Allori dei festival
Il plugin genera allori tipografici eleganti (corona disegnata, stato, festival, sezione, anno).
Le diciture sono nella lingua del festival: «Selezione Ufficiale», «Sélection Officielle»,
«Official Selection». Conosce Venezia, Cannes, Berlinale, Locarno, Roma, Torino, Sundance, TIFF,
Rotterdam, San Sebastián, Karlovy Vary, Clermont-Ferrand, Tribeca, SXSW, Annecy, IDFA, CPH:DOX,
Visions du Réel, Biografilm, Giffoni e Bif&st. Le sezioni parallele (SIC, Giornate, Quinzaine,
Semaine, ACID) sono intestate correttamente.

**Se il festival ti fornisce l'alloro ufficiale, usa quello** (pulsante *Usa alloro ufficiale*): è
la regola d'uso di molti festival.

## Videoclip, spot, social verticale
- **Videoclip**:
  - apertura «ARTISTA – «Titolo»» come lower third;
  - crediti finali brevi (regia, produzione, commissioner, etichetta, reparti);
  - **℗** per la registrazione e **©** per il video, su righe separate;
  - versione verticale con un clic, scegliendo la destinazione 9:16.
- **Social verticale**: la safe area tiene conto dell'interfaccia di TikTok/Reels (pulsanti a
  destra, didascalie in basso); le sezioni affiancate diventano automaticamente impilate.

---

## Cosa sa fare (riepilogo)
- **10 preset**:
  - Italia cinema e TV;
  - USA WGA/DGA;
  - USA/streaming;
  - coproduzione europea;
  - corto/festival;
  - documentario;
  - videoclip;
  - spot/corporate;
  - social verticale.
- **Ricerca sugli standard** con le fonti in [`docs/research/`](docs/research/README.md):
  - MiC/DGCA, tax credit e dichiarazione IA, Film Commission;
  - Eurimages, Europa Creativa MEDIA, CNC, FFA, ICAA;
  - WGA, DGA, PGA, American Humane;
  - EBU/SMPTE/Netflix, safe area social;
  - diritti musicali, festival, videoclip, tipografia, loghi.
- **Diciture in 5 lingue** (it, en, fr, de, es) secondo il tipo di accordo: musica, location,
  noleggi, repertorio, prodotti e diciture legali.
- **Impaginazione**:
  - colonna singola, due colonne, 2–3 gruppi affiancati, griglie, nomi multicolonna;
  - cast, brani, loghi bilanciati per peso ottico;
  - foto/video di backstage in riga o in una corsia laterale;
  - cartelli che si dividono da soli se un elenco non entra.
- **15 profili di destinazione**: cinema DCI flat/scope 2K/4K, TV EBU/SMPTE, streaming, 9:16
  (con zone UI), 4:5, 1:1, verticale 4K.
- **10 set di font**: 8 gratuiti inclusi e installati automaticamente, più 2 solo di sistema.
  Ogni stile resta personalizzabile (font, dimensione, colore, maiuscole, spaziatura, interlinea).
- **Interfaccia a 3 passi** con segnaposto NOME COGNOME; le opzioni avanzate stanno nella scheda «Aspetto e avanzate».
- **Import da CSV/Excel** (modello generabile dal pulsante) e uso da riga di comando, anche senza Resolve.

## Riga di comando (opzionale)
```bash
cd src
python -m drfc presets | destinations | festivals
python -m drfc new short_festival ../mio_corto.drfc.json --title "Il mio corto"
python -m drfc check ../mio_corto.drfc.json
python -m drfc preview ../mio_corto.drfc.json
python -m drfc build ../mio_corto.drfc.json ../out/      # .comp + .setting + anteprima
python -m drfc logos list
```
Esempi pronti in [`examples/`](examples/): corto su sfondo bianco con allori, videoclip
orizzontale e verticale, corto festival, lungometraggio USA.

## Domande frequenti
| Domanda | Risposta |
|---|---|
| La finestra compare e sparisce / errori | Aggiorna all'ultima versione. Se capita ancora, manda a Ivan il file `drfc.log` (Windows: `%APPDATA%\DR-FilmCredits`, macOS: `~/Library/Application Support/DR-FilmCredits`, Linux: `~/.config/DR-FilmCredits`): contiene l'errore. In caso di errore il pannello mostra anche una finestra con il testo. |
| Non vedo la voce nel menu Scripts | Riavvia Resolve; controlla di aver lanciato l'installer e di avere Python 3. |
| «Font non trovati» nella verifica | Rilancia l'installer (installa i font) oppure scegli un set «solo sistema». |
| Logo «da richiedere» | L'ente concede il logo su richiesta: usa *Pagina ufficiale*, poi *Importa file ricevuto*. |
| Ho spostato o modificato una clip a mano | *Aggiorna solo le modifiche* mantiene posizione, proprietà e nodi aggiunti. Per non toccarla mai più: **Blocca**. |
| Voglio tornare alla versione precedente | Nella pagina Fusion del clip scegli il comp `…_prev`. |
| La clip è più corta del rullo | Rara: l'esito te lo segnala; allunga la coda della clip fino alla durata indicata. |
| Le diciture legali sono vincolanti? | Sono modelli basati sulle fonti citate: la formula vincolante è quella del tuo contratto o bando. |

## Per sviluppatori
Python puro, nessuna dipendenza.
- **Test:** `python -m pytest`. Coprono motore, writer Fusion, diciture, preset, loghi, allori,
  e wizard e bridge contro un Resolve simulato.
- **Rigenerare gli asset:**
  - allori: `python -m drfc.laurels`;
  - Title: `python -m drfc.templates templates/`;
  - font: `python tools/fetch_fonts.py`;
  - release: `python tools/make_release.py`.
- **Architettura e dettagli:** [`docs/GUIDA.md`](docs/GUIDA.md).

**Limiti noti:** l'inserimento in timeline è stato verificato contro un Resolve simulato. Alla
prima installazione fai una prova su un rullo breve. La calibrazione automatica legge da script
l'immagine di un Text+ di prova: se Resolve non lo permette si usano i valori standard (al
massimo i caratteri risultano leggermente più grandi o più piccoli del previsto); in
modalità Avanzata c'è «Ricalibra Text+».

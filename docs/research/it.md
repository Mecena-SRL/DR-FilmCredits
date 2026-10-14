# Italia

## 1. Ordine dei titoli [Prassi]

### Titoli di testa (lungometraggio cinema)
Ordine tipico, dal primo all'ultimo cartello:

1. Distribuzione: «{Distributore} presenta»
2. Produzione: «Una produzione {Società}» / «{Società} presenta»
3. Coproduzioni e partecipazioni: «In coproduzione con…», «In collaborazione con Rai Cinema»,
   «Con la partecipazione di…»
4. Loghi dei finanziatori quando il bando li richiede in testa (vedi §2)
5. «Un film di {Regista}» (credito d'autore, facoltativo)
6. Cast principale (un nome per cartello o a coppie; l'ordine è negoziato nei contratti)
7. **Titolo**
8. Cast «con» / «e con» / «con la partecipazione di»
9. Reparti creativi: casting, musiche, costumi, montaggio, scenografia, fotografia
10. Organizzatore generale, soggetto, sceneggiatura
11. Produttori («Prodotto da»)
12. **Regia** (ultimo cartello prima del film)

### Titoli di coda
1. Ripetizione dei crediti principali (regia, sceneggiatura, produzione) se il film non ha titoli di testa completi
2. Interpreti e personaggi (attore a sinistra, personaggio a destra; ordine di contratto o di apparizione)
3. Produzione: produttore esecutivo, line producer, organizzatore generale, direttore di produzione,
   ispettori, coordinamento, segreteria, assistenti, runner
4. Reparti in ordine "di set": regia (aiuto, assistenti, segretaria di edizione), fotografia,
   elettricisti, macchinisti, suono, scenografia, costumi, trucco e acconciature, location,
   trasporti, catering
5. Post-produzione: montaggio, color, VFX, post-produzione audio, musica
6. Amministrazione, legale, ufficio stampa
7. Brani musicali (vedi [music-rights.md](music-rights.md))
8. Location, mezzi tecnici, repertorio, prodotti
9. Ringraziamenti
10. Loghi (finanziatori pubblici, Film Commission, partner)
11. Diciture legali: sostegno del MiC, dichiarazione sull'uso di IA, finzione, pirateria, ©

Il preset `it_cinema` riproduce questa struttura. `it_tv` è una versione compatta pensata
per le durate che impone il broadcaster.

## 2. Ministero della Cultura – Direzione Generale Cinema e Audiovisivo

### Tax credit produzione nazionale (D.I. 10 luglio 2024) [Obbligo]
- Il beneficiario deve inserire **nei titoli e nei materiali promozionali** il **logo e il
  nome del Ministero della Cultura** e una dicitura che specifichi che l'opera è stata
  realizzata con il contributo del Fondo per lo sviluppo degli investimenti nel cinema e
  nell'audiovisivo. Se manca, il beneficio decade.
- Il logo si richiede alla DGCA (pagina «Logo DGCA»). Contiene già il nome del MiC.
- Il plugin: flag `mic_tax_credit` nel progetto → il validatore richiede la dicitura
  `@mic_tax_credit` e un logo con tag `mic`. Il testo della dicitura è modificabile:
  **verificare la formula esatta nel decreto e nel bando applicabili**.

### Intelligenza artificiale [Obbligo, da verificare per i decreti 2025]
- Dal 2024 il beneficiario deve **dichiarare nei titoli di testa o di coda** le parti dell'opera
  o le fasi di lavorazione in cui sono stati usati sistemi di IA, pena la decadenza dal credito
  (fonti: Osborne Clarke, Giornalettismo, sintesi del D.I. 2024).
- Il plugin: casella «Nell'opera è stata usata l'IA» + campo «Per…». La dicitura
  `@ai_disclosure` viene aggiunta in automatico ai titoli di coda.

### Attrazione di investimenti esteri e produzioni esecutive [Obbligo]
- Opere straniere che usano il tax credit italiano: logo del MiC **nei titoli di coda** (obbligo
  da prevedere nel contratto).
- Produzioni esecutive: logo e dicitura **"With the support of the Italian Tax Credit"** nei
  titoli di coda e nei materiali promozionali, con pari rilievo rispetto al produttore esecutivo.
  Il plugin ha la dicitura `@italian_tax_credit_foreign` (in inglese in tutte le lingue).

### Contributi selettivi [Obbligo]
- Formula storica: «con il sostegno della Direzione generale Cinema e audiovisivo» accanto al logo,
  nei titoli di testa e/o di coda; per i bandi dal 2021 il logo è obbligatorio pena decadenza.

### Interesse culturale
- Dicitura disponibile: `@cultural_interest`. Il riconoscimento non comporta da solo un obbligo di
  dicitura: dipende dal contributo collegato.

## 3. Film Commission e fondi regionali [Obbligo per bando]
- Ogni regione ha il proprio regolamento. Esempi:
  - **Marche**: citazione del sostegno con logo nei titoli di testa e/o di coda; in un altro atto la
    dicitura «con il contributo di» + loghi **all'inizio dei titoli di testa o come primo cartello
    dei titoli di coda**, con dimensioni pari agli altri finanziatori istituzionali.
  - **Piemonte**: interventi regolati ai sensi del Reg. UE 651/2014 art. 54 (formula da verificare).
- Il plugin: flag `film_commission` → serve almeno un logo con tag `film_commission`. Dicitura
  `@film_commission name=…`. Posizione e dimensioni si regolano con il blocco Loghi.

## 4. Broadcaster
- RAI, Mediaset, Sky, piattaforme: le regole di durata, font e posizione stanno nelle specifiche
  di consegna del singolo contratto (non pubbliche). Riferimento tecnico generale: EBU R95 per le
  safe area (vedi [broadcast-streaming.md](broadcast-streaming.md)).
- **SRG SSR** (Svizzera) ha un regolamento pubblico sull'obbligo di citazione nei titoli dei film
  coprodotti (2024–2027, anche in italiano): utile come modello.

## Fonti
- [DGCA – Logo](https://cinema.cultura.gov.it/per-gli-utenti/come-fare/logo-dgca/)
- [D.I. MiC-MEF tax credit produzione (2024)](https://cinema.cultura.gov.it/wp-content/uploads/2024/09/rep_-225___DM_MIC_MEF_nuovo_tax_credit_produzione_ex_art_15_L_220_2016___Decreto_controfirmato_Ministro.pdf)
- [DGCA – FAQ produzione](https://cinema.cultura.gov.it/dgca-incontra/faq-domande-frequenti/servizio-iii/produzione-cinema-tv-web-nazionale-e-internazionale/)
- [DGCA – Chiarimenti D.I. 10 luglio 2024](https://cinema.cultura.gov.it/dgca-incontra/faq-domande-frequenti/servizio-iii/chiarimenti-sul-d-i-10-luglio-2024/)
- [Vademecum tax credit produzione nazionale 2024](https://cinema.cultura.gov.it/wp-content/uploads/dlm_uploads/2024/11/Vademecum_TC_Produzione-nazionale_2024_20241030-1.pdf)
- [Osborne Clarke – Il nuovo decreto tax credit](https://www.osborneclarke.com/it/insights/il-nuovo-decreto-tax-credit-le-imprese-di-produzione-cinematografica-e-audiovisiva)
- [Giornalettismo – Riforma tax credit](https://www.giornalettismo.com/riforma-tax-credit-cinema/)
- [Regione Marche – Obblighi del beneficiario](https://bandi.regione.marche.it/Allegati/7530/ALLEGATO%20H%20OBBLIGHI%20DEL%20BENEFICIARIO-signed.pdf)
- [Regione Piemonte – Linee di indirizzo FCTP](https://www.regione.piemonte.it/web/media/6407/download)
- [SRG SSR – Regolamento obbligo di citazione 2024–2027](https://www.srgssr.ch/fileadmin/dam/documents/Kultur/Reglement-Nennungspflicht_KINO_2024-2027_it.pdf)

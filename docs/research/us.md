# Stati Uniti

## WGA – crediti di scrittura [Obbligo per produzioni WGA]
- Forme ammesse: **Written by**, **Screenplay by**, **Story by**, **Screen Story by**,
  **Adaptation by**, **Narration Written by**, **Based on Characters Created by**. Altre forme
  solo con deroga.
- **"Written by"** = stessi autori per soggetto e sceneggiatura.
- **"&"** = squadra di scrittura (anche se formata per un solo progetto); **"and"** = autori che
  hanno lavorato separatamente (di solito uno riscrive l'altro). La convenzione non dipende dalla
  preferenza degli autori.
- La forma del credito va indicata nella proposta di crediti, non solo i nomi.
- Il plugin: opzione **Squadra (&)** sui crediti; il validatore suggerisce di attivarla quando ci
  sono più autori (`wga_team_hint`).

## DGA – regia [Obbligo per produzioni DGA]
- **"Directed by"** è l'unica forma ammessa a schermo e in pubblicità; "Director" e derivati sono
  riservati a regista, aiuto regista, direttore della fotografia e art director.
- Credito "possessivo" (**"A Film by"**): negoziabile; sconsigliato al primo lungometraggio salvo
  che il regista abbia portato e sviluppato il progetto. Con **6 o più crediti personali** il
  regista ha diritto anche a "A Film By" sopra il titolo, non più piccolo di "Directed By"
  (Sideletter 27).
- [Prassi] Nei titoli di testa il credito di regia è **l'ultimo prima del film**; nei titoli di
  coda è il primo. Il validatore (`director_form`) avvisa se nei cartelli di testa non è l'ultimo.

## PGA – "p.g.a." [Obbligo d'uso]
- Marchio di certificazione gratuito concesso dalla PGA ai produttori che hanno svolto la
  maggioranza delle funzioni di produzione; si mette dopo il nome nei titoli e nella pubblicità,
  progetto per progetto. Non richiede l'iscrizione alla PGA. Nel plugin basta scrivere
  `Nome Cognome, p.g.a.`.

## Ordine dei titoli [Prassi]
- **Main titles**: studio/distributore presenta → casa di produzione → "A Film by" → cast
  principale → titolo → casting → musica → costumi → montaggio → scenografia → fotografia →
  produttori esecutivi → produttori → sceneggiatura → regia.
- **End crawl**: ripetizione dei crediti principali (regia, sceneggiatura, produttori, …) su
  "cards" o in testa al rullo → cast (personaggio … attore) → troupe per reparto → seconda unità →
  VFX → musica (brani) → ringraziamenti → loghi (sindacati, studios) → diciture legali.

## Sindacati e marchi [Obbligo da contratto]
- IATSE, Teamsters e altri: il "bug" (logo sindacale) va nei titoli secondo l'accordo collettivo.
  Dicitura modificabile `@union_bug`.
- **SAG-AFTRA**: crediti degli interpreti secondo contratto; presenza di animali → monitoraggio
  American Humane per le produzioni SAG.
- **MPA**: numero di certificato di classificazione nei titoli di coda (`@mpa_cert`) [Prassi, da verificare].

## American Humane – "No Animals Were Harmed®" [Obbligo d'uso]
- È un marchio: si usa solo se American Humane ha monitorato il set e ha visionato il film prima
  dell'uscita. L'uso non autorizzato ha prodotto diffide.
- Il plugin separa `@animals_aha` (formula certificata, con numero) da `@animals_generic`
  (dichiarazione generica, per produzioni non certificate).

## Copyright e finzione [Prassi]
- "© {anno} {titolare}. All rights reserved." + disclaimer di finzione + avviso anti-pirateria,
  in fondo al rullo.

## Fonti
- [WGA – Screen Credits Manual](https://www.wga.org/uploadedfiles/credits/manuals/screenscredits_manual10.pdf)
- [WGA – Screen Credits Manual 2021](https://origin.www.wga.org/uploadedfiles/credits/manuals/screenscredits_manual21.pdf)
- [WGA – Credits Process Guide 2020](https://origin.www.wga.org/uploadedfiles/credits/manuals/scpg2020.pdf)
- [DGA – Credits](https://dga.org/The-Guild/Departments/Credits)
- [DGA – Creative Rights: Credits](https://dga.org/Contracts/Creative-Rights/Credits)
- [DGA – Basic Agreement 2020, Art. 8](https://edge.sitecorecloud.io/directorsguf4d4-dga2c79-dgaprod1615-f6e3/media/Files/Contracts/Agreements/2020-Basic-Agreement/DGA_BA2020_08_Article008.pdf)
- [DGA – Sideletter 27 (2017)](https://edge.sitecorecloud.io/directorsguf4d4-dga2c79-dgaprod1615-f6e3/media/Files/Contracts/Agreements/2017_BasicAgreement/064_BA2017-Sideletter-027s.pdf)
- [PGA – Producers Mark](https://producersguild.org/producers-mark/)
- [American Humane – Certification](https://old.humanehollywood.org/index.php/on-the-set/certification-definition)
- [dvm360 – Uso improprio del disclaimer](https://dvm360.com/view/movies-misuse-no-animals-were-harmed-disclaimer)

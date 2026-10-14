# Broadcast e streaming: leggibilità, safe area, durata, scorrimento

## Safe area
- **EBU R95**: per HD 16:9 la *title safe* è il 5% per lato (96 × 54 px a 1920×1080), la
  *action safe* il 3,5% (67 × 38 px). Le specifiche di consegna europee richiedono grafiche e
  titoli entro queste aree e senza errori di battitura. **[Obbligo nelle consegne TV]**
- **Netflix**: nessun vincolo rigido, raccomanda SMPTE (title safe 90%, action safe 93%). Nei
  titoli di testa, un credito Netflix deve avere stesso font e dimensione dei crediti attorno.
- **SMPTE RP 218**: metodo di riferimento per le aree di sicurezza.
- Il plugin: `format.safe_title` (default 0.9). Il motore manda a capo le righe e segnala
  qualsiasi testo che esca dalla safe area.

## Durata
- Non esiste uno standard di settore (ITV lo ha dichiarato esplicitamente). Ogni broadcaster lo
  fissa nelle sue linee guida: per esempio **Virgin Media Television** (Irlanda) chiede una
  sequenza di crediti tra **27 e 33 secondi** con font Arial; **RTÉ** chiede un formato
  standard perché restino leggibili quando vengono ridimensionati; la **BBC** ha smesso di
  comprimere i crediti in un riquadro per lasciarli a piena dimensione.
- Il plugin: preset TV con durata obiettivo e **Adatta a durata** (velocità o spaziatura) per
  centrare il valore esatto richiesto dal contratto.

## Velocità di scorrimento e judder [Prassi tecnica]
- Il rullo deve muoversi di un **numero intero di pixel per fotogramma**: valori frazionari
  (es. 6,32 px/frame) producono tremolio sui caratteri sottili. Un valore intorno a **4 px/frame**
  è considerato sicuro tra 24 e 30 fps a 1080p; sopra ~10 px/frame diventa difficile da leggere.
- Leggibilità: una riga dovrebbe restare a schermo almeno **~7 secondi** dal basso all'alto.
- Bianco su nero è il caso peggiore per lo strobing; rallentare molto rende il judder più visibile.
- La resa va verificata con un render a piena risoluzione in un player, non nell'anteprima
  dell'editor.
- Il plugin:
  - preset **lenta / normale / veloce** = 15 / 11 / 8 secondi per attraversare lo schermo,
    convertiti in px/frame **interi** per la risoluzione e il frame rate della timeline
    (1080p24: 3 / 4 / 6 px/frame; UHD: il doppio);
  - "Adatta a durata" sceglie la velocità intera più bassa che sta nel tempo e recupera i frame
    residui con la pausa finale → durata esatta senza velocità frazionarie;
  - avviso se una riga resta a schermo meno di 6 s.

## Fonti
- [EBU – Safe areas for widescreen transmission](https://tech-qual.ebu.ch/publications/trev_280-baker)
- [Specifiche tecniche di consegna Europa (EBU R95)](https://help-advancedtv.cape.io/hc/it/articles/4407971511185-Specifiche-Tecniche-Europa)
- [SMPTE RP 218:2009](https://reference.globalspec.com/ref/11004457/rp-218-2009)
- [Netflix – Title Safe and Safe Action](https://backlothelp.netflix.com/hc/en-us/articles/4406208331923-Title-Safe-and-Safe-Action-Best-Practices)
- [Netflix – Credit Incorporation Guidelines](https://backlothelp.netflix.com/hc/en-us/articles/360058735634-Netflix-Credit-Incorporation-Guidelines)
- [Virgin Media Television – Credit and Presentation Guidelines](https://virginmediatelevision.ie/content/downloads/commissioning/Virgin-Media-Television-Credit-and-Presentation-Guidelines.pdf)
- [RTÉ – End credit guidelines](https://about.rte.ie/commissioning/author/kennym/page/2)
- [The Stage – BBC stops squeezing end credits](https://thestage.co.uk/news/bbc-stops-squeezing-end-credits-to-give-creatives-proper-bow)
- [UK Parliament – Select Committee on Communications (ITV sulla durata dei crediti)](https://publications.parliament.uk/pa/ld200708/ldselect/ldcomuni/122/7120607.htm)
- [Larry Jordan – Create a smooth credit roll](https://larryjordan.com/articles/create-a-smooth-credit-roll/)
- [Adobe Community – Rolling credits judder](https://community.adobe.com/t5/after-effects/rolling-credits-issue-updated/td-p/10230983)

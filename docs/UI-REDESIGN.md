# FilmCredits: revisione UI e inserimento in timeline

## Decisioni implementate

- Vista Progetto, Editor, Timeline e Aspetto con una sola vista nativa mostrata alla volta.
- Stile scuro coerente, pulsanti compatti, elenco senza righe duplicate dei cartelli,
  bozza del contenuto al centro e proprietà a destra.
- Salva scrive il progetto e non cambia selezione. Frecce di navigazione separate.
- Quattro zone: apertura, testa, chiusura e rullo. La zona può essere cambiata nelle
  proprietà; passare tra rullo e cartelli sposta il blocco in una sequenza compatibile.
- Editor dei cartelli delle società con funzione, formula proposta, testo concordato,
  riferimento e approvazione. Non è una certificazione della contrattualistica.
- Filmstrip V1/V2 con timecode reali, due finestre temporali separate da `//`, apertura
  della scala completa e collegamenti ai singoli elementi. Prima della generazione
  le posizioni sono esplicitamente indicative. V1/V2 sono corsie schematiche.
- Genera, Aggiorna e gestione delle rimozioni hanno operazioni e riepiloghi distinti.
- Nuove clip viola su tracce superiori; nessun ripple implicito.
- Identità del progetto titoli e della clip; stato distinto per progetto/timeline Resolve.
- Copie manuali indipendenti; nessuna eliminazione automatica dei duplicati.
- Durata manuale conservata per default, con segnalazione dell'eventuale taglio del rullo.
- Sostituzioni di durata preparate prima di eliminare l'originale e controllo dei conflitti.
- Riepilogo invalidato se cambia il progetto, la timeline o la posizione/durata delle clip.

## Specifica della timeline compatta

Il pannello mostra da inizio timeline (incluso frameleader) a dopo il termine del film
e degli ultimi crediti. La parte iniziale e quella finale usano scale indipendenti;
`//` indica l'intervallo non mostrato. Per un film breve che non ha un intervallo
centrale omissibile, si usa una scala continua. Il formato drop-frame è supportato.
I blocchi mantengono gli estremi temporali del modello; le etichette vengono abbreviate.
Le sovrapposizioni vengono indicate come più titoli: il primo collegamento apre il
primo elemento, gli altri rimangono accessibili nell'elenco. Non è un editor di trim.

## Vincoli e lavori successivi

1. **Inspector Resolve:** esporre nome, ruolo e altre proprietà per modificare i titoli
   direttamente dalla clip. Definire prima una sincronizzazione a due vie e la gestione
   dei conflitti con il progetto dello script; non sovrascrivere silenziosamente gli edit.
2. Anteprima interna del rendering Fusion e dei loghi, oltre alla bozza testuale.
3. Moduli dedicati per cast, musiche e accordi, mantenendo l'importazione testuale rapida.
4. Schede per requisiti applicabili, fonte/versione e override contrattuale, distinguendo
   obblighi, prassi e indicazioni da verificare. Non dedurre l'applicabilità WGA/DGA dal paese.
5. Affinare tipografia, tooltip e densità della filmstrip tramite screenshot nativi;
   la sua versione finale non ha completato il controllo visivo per disconnessione CUA.
6. Localizzazione completa: nuovi testi principali sono italiano/inglese; le altre lingue
   usano il fallback inglese, alcuni messaggi operativi restano in italiano.
7. Recupero guidato di una clip mancante, con scelta esplicita tra ricollegare e rigenerare.
8. Collocazione automatica dei nuovi titoli in base a punti definiti dal progetto; ora
   l'utente indica i timecode delle quattro zone e approva il riepilogo.

Lo spostamento generale del montaggio resta manuale: non ricostruire le clip originali
tramite AppendToTimeline, perché non garantisce la conservazione di effetti e automazioni.

## Verifica manuale prima del merge

- Avvio e navigazione delle quattro viste su Mac, Windows e Linux; nessuna finestra fuori schermo.
- Clic su un blocco della filmstrip, scala completa/compatta e timecode drop-frame.
- Prima generazione su una timeline duplicata con frameleader fino a 01:00:02:00.
- Film e audio restano fermi; le nuove tracce sono sopra le esistenti.
- Spostare, rinominare, accorciare e copiare una clip: aggiornare solo l'originale collegato.
- Aggiornare con Glow aggiunto manualmente e con un nodo DRFC_ modificato: verificare e
  documentare quali parti sono conservate e quali vengono rigenerate.
- Rimuovere un elemento dal configuratore, conservare/scollegare o rimuovere la sua clip.
- Provare durata calcolata, conflitto con la clip successiva e inserimento fallito.
- Salvare, riaprire, cambiare timeline e tornare a quella originale: i collegamenti restano separati.

La finestra usata durante lo sviluppo era una preview senza accesso alla timeline del
progetto aperto. Nessun montaggio è stato modificato per la verifica visiva.

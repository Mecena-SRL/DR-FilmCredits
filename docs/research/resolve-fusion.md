# Note tecniche: API di DaVinci Resolve e Fusion Text+

## Inserimento con durata esatta
- `Timeline.InsertFusionCompositionIntoTimeline()` **non accetta una durata**: il clip nasce con la
  "Standard Generator Duration" delle preferenze (forum Blackmagic, 2025).
- Soluzione adottata: un **supporto trasparente** (PNG alla risoluzione della timeline) aggiunto con
  `MediaPool.AppendToTimeline([{mediaPoolItem, startFrame, endFrame, trackIndex, recordFrame}])`.
  La durata viene verificata con `TimelineItem.GetDuration()`; se Resolve non estende il fermo
  immagine, si importa una **sequenza di N immagini** (hardlink: occupa lo spazio di un solo file)
  con `ImportMedia([{FilePath, StartIndex, EndIndex}])`.
- Sul clip si importa il comp generato: `TimelineItem.ImportFusionComp(path)`; il frame iniziale
  si legge da `comp.GetAttrs()["COMPN_RenderStart"]` e, se diverso da 0, il comp viene rigenerato
  con l'offset giusto.
- Aggiornamento: i clip generati hanno nome `DRFC_<titolo>_<sequenza>_holder…`; rigenerando, i
  precedenti vengono rimossi (`Timeline.DeleteClips`) e il nuovo prende la stessa posizione.
- Fallback: `.setting` da incollare nella pagina Fusion (Ctrl+V).

## Text+
- `Size` è relativo alla risoluzione, non in punti. Misure empiriche della community:
  ~0,000727 per punto in 16:9 e ~0,000682 in DCI 17:9, cioè `em_px ≈ Size × Width / 1,08`.
  Il plugin usa questo valore e permette di **misurarlo** con "Calibra Text+" (rende un Text+ di
  prova e ne legge il riquadro dei pixel).
- Allineamento: `HorizontalLeftCenterRight` (-1/0/1) ancora il testo; in modalità automatica ogni
  riga delle colonne laterali è un Text+ ancorato al bordo, così l'allineamento non dipende dalla
  giustificazione multiriga.
- `LineSpacing` moltiplica l'interlinea naturale del font: il motore la calcola dalle metriche
  `hhea` del file del font per mantenere le colonne sulla stessa linea di base.

## Scorrimento
- Un solo `Transform` di controllo (`DRFC_Scroll`) con un'**espressione** min/max: tutte le posizioni
  dipendono da `DRFC_Scroll.Center.Y`. Le pause sono termini `min(max(t − a, 0), h)`: niente
  keyframe da gestire. Ogni strumento ha `GlobalIn/GlobalOut` limitati ai frame in cui è visibile.

## Fonti
- [Resolve Scripting README (copia pubblica)](https://gist.github.com/Manouchehri/e32461dccd824167bac8358bb21c8040)
- [Forum Blackmagic – InsertFusionCompositionIntoTimeline: controllo della durata](https://forum.blackmagicdesign.com/viewtopic.php?p=1144261)
- [Forum Blackmagic – Dimensione Text+ in punti](https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=110605)
- [Forum Blackmagic – Durata dei nodi Fusion in timeline](https://forum.blackmagicdesign.com/viewtopic.php?p=773222)

# Crediti musicali e diciture per tipo di accordo

## Struttura di un credito brano [Prassi]
```
"Titolo del brano"
Written by Autore 1 & Autore 2      (autori/compositori; "Music by" / "Lyrics by" se distinti)
Performed by Interprete
Published by Editore                (opzionale)
Courtesy of Etichetta               (titolare del master)
By arrangement with Agente          (agente/licenziante intermedio, opzionale)
```
Nei credit list reali (cue sheet, IMDb soundtrack) compaiono anche "Under license from",
"Used by permission of" (brani non legati a un'etichetta) e note di posizione. La formula
esatta la stabilisce il contratto di licenza: **il campo "override" permette di scriverla a mano**.

## Diciture per tipo di accordo (campo `agreement`)

| Accordo | Quando | it | en |
|---|---|---|---|
| `original` | musica composta per il film | Musica originale composta per il film | Original music composed for the film |
| `licensed` | licenza sync/master a pagamento | Su licenza di X | Courtesy of X |
| `licensed_under` | licenza tramite un licenziante | Su licenza di X | Under license from X |
| `courtesy` | **concessione gratuita** | Per gentile concessione di X | Used by kind permission of X |
| `artist_owned` | l'artista possiede i diritti e li concede | Per gentile concessione dell'artista | Courtesy of the artist |
| `library` | musica di libreria/produzione | Musica di repertorio per gentile concessione di X | Courtesy of X |
| `public_domain` | brano tradizionale | Tradizionale | Traditional |
| `creative_commons` | licenza CC | Licenza CC BY 4.0 – X | Licensed under CC BY 4.0 – X |

Stesse voci in francese, tedesco e spagnolo in `src/drfc/data/phrases/`.

### Note operative
- Sincronizzazione (opera: autori/editori) e master (registrazione: etichetta) sono **due licenze
  diverse**: un brano può avere editore "per gentile concessione" e master "su licenza". In quel
  caso usare `publisher` + `licensor` o le righe `extra`.
- **Creative Commons**: la licenza (es. CC BY 4.0) e l'attribuzione sono obbligatorie; il
  validatore le richiede.
- In Italia le edizioni musicali si citano spesso come «Edizioni musicali X»; i diritti d'autore
  sono gestiti da SIAE (dicitura opzionale `@music_rights_society society=SIAE`).
- Più autori in squadra: `team: si` → "A & B" (convenzione WGA estesa per analogia).

## Fonti
- Esempi di credit list: [IMDb – This Is the End, soundtrack](https://www.imdb.com/title/tt1245492/soundtrack),
  [IMDb – soundtrack credits](https://www.imdb.com/title/tt0109830/soundtrack)
- Prassi di licensing e cue sheet: contratti di sincronizzazione e master del singolo progetto
  (fonte vincolante).

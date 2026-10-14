# Location, noleggi, repertorio, prodotti e diciture legali

## Location (`agreements` kind=`location`)
| Accordo | Uso | it |
|---|---|---|
| `paid` | location a pagamento: basta il nome | Villa Rossi |
| `free` | concessa gratuitamente da privati | Villa Rossi, per gentile concessione di Famiglia Rossi |
| `public` | spazi pubblici con collaborazione di enti | Porto di X, con la gentile collaborazione di Comune di X |
| `thanks` | solo ringraziamento | Villa Rossi |

## Mezzi tecnici / noleggi (kind=`rental`)
| Accordo | it | en |
|---|---|---|
| `paid` | Attrezzature fornite da X | Equipment provided by X |
| `free` | Attrezzature gentilmente concesse da X | Equipment kindly provided by X |
| `discount` | Con il supporto tecnico di X | With the technical support of X |
| `sponsor` | In collaborazione con X | In collaboration with X |

## Materiali di repertorio (kind=`archive`) – fondamentale nei documentari
| Accordo | it |
|---|---|
| `licensed` | Immagini di repertorio su licenza di X |
| `free` | Immagini di repertorio per gentile concessione di X |
| `public_domain` | Immagini di repertorio: X (pubblico dominio) |

## Prodotti e opere d'arte (kind=`product`, `artwork`)
- Product placement: elenco marchi nei titoli + dicitura `@product_placement`. In TV la normativa
  sui servizi media audiovisivi richiede di segnalare l'inserimento di prodotti; verificare le
  regole del broadcaster.
- Opere d'arte riprodotte: «su licenza di» / «per gentile concessione di».

## Diciture legali disponibili (`@chiave`)
| Chiave | Uso |
|---|---|
| `copyright` | © anno titolare. Tutti i diritti riservati. |
| `fiction`, `fiction_true_story` | disclaimer di finzione / ispirato a fatti reali |
| `piracy` | avviso anti-pirateria |
| `ai_disclosure`, `no_ai` | dichiarazione uso IA (obbligatoria per il tax credit italiano) |
| `animals_generic`, `animals_aha` | animali (AHA solo con certificazione) |
| `product_placement`, `no_endorsement` | prodotti |
| `music_rights_society` | società di gestione diritti (SIAE, SACEM, GEMA…) |
| `mic_tax_credit`, `cultural_interest`, `italian_tax_credit_foreign` | MiC |
| `creative_europe`, `eurimages`, `film_commission`, `cnc`, `ffa`, `dfff`, `icaa` | fondi |
| `rating`, `mpa_cert`, `union_bug`, `country_of_origin` | varie |

Tutte esistono in 5 lingue (it, en, fr, de, es); le chiavi mancanti in una lingua usano
l'inglese. Ogni dicitura si può sostituire con testo libero nel blocco.

## Assicurazioni e garanzie
- Completion bond e assicuratori sono spesso citati per contratto: usare un elenco
  (`list`, reparto `insurance`) o testo libero.

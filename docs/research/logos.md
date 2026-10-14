# Loghi: registro, regole e aggiornamento

Il registro `src/drfc/data/logos/registry.json` elenca **41 enti**: MiC/DGCA, Italian Tax Credit,
tutte le Film Commission regionali, Rai/Rai Cinema, Cinecittà/Luce, SIAE, Creative Europe MEDIA,
emblema UE, Eurimages, CNC, FFA, DFFF, ICAA, BFI, UFC (CH), SRG SSR, ÖFI, PGA, American Humane.

Per ciascuno: pagina ufficiale, eventuali URL diretti, se il logo **va richiesto**, regole d'uso
note, data di verifica.

## Perché i file non sono inclusi
- Molti enti **concedono il logo solo su richiesta** (MiC tramite DGCA; CNC previa approvazione;
  Film Commission ai beneficiari) e ne regolano l'uso.
- I loghi sono marchi: vanno presi dalla fonte ufficiale nella versione aggiornata.
Per questo il plugin ha un **kit loghi locale** e un **aggiornatore**:

```
python -m drfc logos list                 # stato di ogni logo (pronto / da scaricare / da richiedere / da convertire)
python -m drfc logos update               # scarica i loghi con URL diretto (ETag: scarica solo se cambiati)
python -m drfc logos open mic_dgca        # apre la pagina ufficiale
python -m drfc logos import mic_dgca ~/Downloads/logo_mic.zip   # importa file o ZIP ricevuto
python -m drfc logos update-registry      # aggiorna l'elenco enti dal repository GitHub
```
Le stesse funzioni sono nel pannello (pagina Loghi del blocco).

## Regole principali
| Ente | Regola |
|---|---|
| MiC – DGCA | logo + nome + dicitura nei titoli e nei promozionali (tax credit, pena decadenza) |
| Italian Tax Credit | logo + «With the support of the Italian Tax Credit» nei titoli di coda |
| Film Commission | da bando (es. Marche: inizio titoli di testa o primo cartello di coda, stesse dimensioni degli altri enti) |
| Creative Europe MEDIA | testa: almeno «Co-funded by the European Union»; coda: dicitura + logo MEDIA |
| Emblema UE | ≥ 1 cm, «European Union» per esteso, «Funded by / Co-funded by the European Union» |
| Eurimages | titoli di testa, subito dopo i produttori; bozza da approvare |
| CNC | uso previa approvazione (logo@cnc.fr) |

## Formati
Fusion **non legge SVG/PDF**: servono PNG con trasparenza (meglio due varianti: chiara per sfondi
scuri, scura per sfondi chiari). L'aggiornatore estrae i PNG dagli ZIP e segnala SVG/PDF da
convertire.

## Fonti
- [DGCA – Logo](https://cinema.cultura.gov.it/per-gli-utenti/come-fare/logo-dgca/)
- [EACEA – Creative Europe MEDIA visual identity](https://www.eacea.ec.europa.eu/grants/visual-identity/creative-europe-media-visual-identity_en)
- [DFI – Logo Creative Europe MEDIA (2021-2027)](https://www.dfi.dk/node/49413)
- [Emblema UE – regole (2012)](https://www.ypes.gr/UserFiles/f0ff9297-f516-40ff-a70e-eca84e2ec9b9/emblem_eu_programm_01082012.pdf)
- [Eurimages – Logo](https://coe.int/web/eurimages/logo) · [CNC – Logo](https://www.cnc.fr/a-propos-du-cnc/logo-du-cnc)
- [Italian Film Commissions](https://filmitalia.org/en/filmcommission/40174) · [Regione Marche – obblighi](https://bandi.regione.marche.it/Allegati/7530/ALLEGATO%20H%20OBBLIGHI%20DEL%20BENEFICIARIO-signed.pdf)

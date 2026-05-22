# Arcanista Tools Backend

Questo micro-backend rende operative due GPT Actions custom:

- `Arcanista PDF Character Sheet Compiler`
- `Arcanista DND 5e Encounter Builder`

## JSON in due parole

JSON è un formato testuale per mandare dati strutturati a un servizio.

Esempio:

```json
{
  "nome": "Elarion",
  "classe": "Mago",
  "livello": 5
}
```

Per le Actions, il GPT crea un JSON con i dati necessari, lo manda al backend, e il backend risponde con un altro JSON.

## Installazione locale

```powershell
cd arcanista_tools_backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8787
```

Health check:

```text
http://127.0.0.1:8787/health
```

## Deploy consigliato su Render

Il progetto include `render.yaml`, quindi è pronto per un deploy Render Blueprint o Web Service.

## Uso per terzi

Se vuoi che funzioni anche per altre persone, il backend deve essere pubblico ma protetto.

Questo progetto usa una API key opzionale:

```text
ARCANISTA_API_KEY
```

Se questa variabile è impostata, gli endpoint `/character-sheet/fill-italian-5e` e `/encounters/build-or-balance-5e-2014` richiedono l'header:

```text
X-API-Key: valore-della-tua-chiave
```

Nel GPT Builder, configura l'Action `Arcanista Tools` con autenticazione API Key:

```text
Auth type: API Key
Header name: X-API-Key
Value: il valore di ARCANISTA_API_KEY
```

Per un GPT pubblico, questa chiave resta configurata nel GPT e gli utenti non devono conoscerla. Se invece vuoi distribuire lo schema ad altre persone perché creino il loro GPT, ciascuna persona dovrebbe deployare il proprio backend o avere una propria chiave.

Attenzione: i PDF generati sono serviti tramite URL nella cartella `/files`. Non inserire dati sensibili reali nei PDF generati. Per un servizio pubblico serio, aggiungere scadenza automatica dei file, pulizia periodica e storage privato.

### Opzione A: deploy manuale Render

1. Crea una repo GitHub con questa cartella come root del progetto.
2. Vai su Render.
3. New > Web Service.
4. Collega la repo GitHub.
5. Imposta:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

6. In Environment aggiungi:

```text
ARCANISTA_API_KEY = una-stringa-lunga-segreta
```

7. Deploy.
8. Render ti darà un URL tipo:

```text
https://arcanista-tools.onrender.com
```

### Opzione B: deploy Blueprint

Se usi il Blueprint, Render leggerà `render.yaml`.

Verifica comunque che:

```text
buildCommand = pip install -r requirements.txt
startCommand = uvicorn app.main:app --host 0.0.0.0 --port $PORT
healthCheckPath = /health
```

## Aggiornare lo schema Action

Dopo il deploy, apri:

```text
../arcanista_tools_combined_action_openapi.yaml
```

e sostituisci:

```text
https://your-arcanista-tools-domain.example.com
```

con l'URL Render reale, per esempio:

```text
https://arcanista-tools.onrender.com
```

Poi incolla lo schema aggiornato nella Action del GPT Builder.

## PDF compiler

Endpoint:

```text
POST /character-sheet/fill-italian-5e
```

Per usare il template vero, metti questo file in:

```text
arcanista_tools_backend/templates/dnd_blankcharactersheet_it.pdf
```

Se il template non c'è, il backend genera comunque un PDF riassuntivo.

Nota: l'overlay sul PDF è una prima versione. Dopo un test visuale sulla scheda italiana, le coordinate possono essere rifinite.

## Encounter builder

Endpoint:

```text
POST /encounters/build-or-balance-5e-2014
```

Riceve party, difficoltà desiderata, ambiente e mostri candidati. Restituisce:

- budget XP;
- difficoltà stimata;
- note di bilanciamento;
- rischi;
- scaling knobs;
- struttura giocabile dell'incontro.

## Uso con GPT Actions

Schema OpenAPI consigliato da incollare nel GPT Builder:

```text
arcanista_tools_combined_action_openapi.yaml
```

Usa questo schema combinato perché il GPT Builder può dare problemi se due azioni diverse puntano allo stesso dominio.

Prima di incollarlo, sostituisci:

```text
https://your-arcanista-tools-domain.example.com
```

con l'URL HTTPS reale del backend deployato.

GPT Actions non possono chiamare `localhost` dal cloud. Per usarle nel Custom GPT serve un deploy pubblico HTTPS, per esempio Render, Railway, Fly.io, Azure, Google Cloud Run o un server tuo.

Importante: il dominio nello schema deve essere tutto minuscolo e deve corrispondere alla root origin che il Builder rileva. Non usare placeholder con maiuscole.

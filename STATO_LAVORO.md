# Stato di lavoro del progetto

Data: 2026-04-08

## 1) Stato attuale

Il repository contiene tre blocchi principali:

1. **SolAI.Pipecat.LLMService**: servizio ASP.NET Core 8 che espone un'API **OpenAI-compatible** con:
   - `GET /health`
   - `GET /v1/models`
   - `POST /v1/chat/completions`
   - Swagger in development su `/swagger`
2. **Client Python Pipecat**:
   - `bot.py`
   - `bot_cuda.py`
   - `bot_xtts.py`
   - `chat_openai_console.py`
3. **Langfuse self-hosted stack + tracing**:
   - `langfuse-web`, `langfuse-worker`, `postgres`, `clickhouse`, `redis`, `minio`
   - i bot Pipecat e `SolAI.Pipecat.LLMService` emettono trace/spans via OTLP verso Langfuse


Verifiche eseguite:
- `dotnet build SolAI.Pipecat.LLMService/SolAI.Pipecat.LLMService.sln` completato con successo
- `docker compose config` completato con successo sul nuovo stack Docker

Nota: il build reale dei container non è stato eseguito in questa sessione perché il daemon Docker non era disponibile.

## 2) Uso attuale

### Stack Docker completo


Il compose espone anche Langfuse UI su `http://localhost:3000` e inizializza un progetto locale con chiavi demo.
I bot Pipecat usano `langfuse_observability.py` per inviare le tracce al backend OTLP self-hosted.
Il file `docker-compose.yml` ora ricostruisce lo stack locale con:
- **ollama** come upstream LLM OpenAI-compatible
- **llmservice** come proxy/API applicativa
- **xtts** come servizio TTS esterno

Avvio tipico:

```bash
docker compose up --build
```

Prima esecuzione:
- `ollama-pull` scarica automaticamente il modello configurato in `OLLAMA_MODEL`
- default del modello: `qwen2.5:3b`

Endpoint locali una volta avviato lo stack:
- Ollama: `http://localhost:11434`
- SolAI LLM Service: `http://localhost:5077`
- XTTS: `http://localhost:8000`

### Servizio .NET in locale

Esecuzione tipica fuori da Docker:

```bash
dotnet run --project SolAI.Pipecat.LLMService/SolAI.Pipecat.LLMService.csproj
```

Configurazione principale:
- sezione `LlmService` in `appsettings.json`
- endpoint di sviluppo: `http://localhost:5077`
- file di esempio richieste: `SolAI.Pipecat.LLMService.http`

### Endpoint esposti

- `GET /v1/models` restituisce i modelli disponibili
- `POST /v1/chat/completions` accetta payload OpenAI-style con `messages`, `stream`, `temperature`, `top_p`, `max_tokens`, `tool_choice`, `tools`, `user`

### Console client

`chat_openai_console.py` è un client testuale contro un endpoint OpenAI-compatible.

Esempio:

```bash
python chat_openai_console.py --base-url http://localhost:5077 --api-key test-key
```

Comandi interni utili:
- `/help`
- `/models`
- `/model [nome]`
- `/system [testo]`
- `/stream on|off`
- `/toolchoice auto|required|none`
- `/reset`
- `/history`
- `/exit`

### Bot Pipecat

I tre bot sono varianti dello stesso flusso:
- STT Whisper
- LLM OpenAI-compatible verso LM Studio / endpoint locale
- TTS Kokoro o XTTS
- trasporto `SmallWebRTCTransport`

Note pratiche:
- `bot.py` usa Whisper `medium` su CPU e Kokoro TTS
- `bot_cuda.py` usa Whisper `large-v3-turbo` su CUDA e Kokoro TTS
- `bot_xtts.py` usa Whisper `large-v3-turbo` e XTTS
- tutti e tre i bot inizializzano Langfuse OTLP tracing all'avvio; per i package di tracing installare `pip install -r requirements-observability.txt`


`bot_xtts.py` richiede anche:
- `XTTS_BASE_URL` (default `http://localhost:8000`)
- `XTTS_VOICE_ID` (default `Ana Florence`)
- container XTTS attivo via `docker-compose.yml`

## 3) Cosa manca / TODO

### Mancanze strutturali
- Aggiunto un `README.md` di quickstart e `.env.example`; resta da completare un manifest Python completo (`requirements.txt`, `pyproject.toml` o equivalente) per l'intero ambiente.

### TODO funzionali
- Rendere configurabili in modo esplicito gli endpoint di upstream LLM e TTS per evitare dipendenze ambientali nascoste.
- Definire un percorso di avvio unico per chi deve solo provare la demo.
- Chiarire che il dataset ticket è demo-only oppure collegarlo a una sorgente reale.

## 4) Bug / rischi concreti osservati

### Rischio 1: endpoint upstream hardcoded fuori dal compose
Nel servizio .NET e nei bot Python l'upstream LLM resta legato a valori hardcoded o semi-hardcoded nel codice/configurazione.

Esempi:
- `LlmServiceOptions.UpstreamEndpoint` default: `http://192.168.45.205:1234/v1`
- `appsettings.json` / `appsettings.Development.json`: stesso endpoint privato
- bot Python: endpoint locale LM Studio impostato nel codice

Effetto:
- fuori dalla rete originale il servizio non parte o non parla con il modello se non viene sovrascritto a runtime
- la demo non è portabile senza modifiche o override di configurazione

### Rischio 2: primo avvio di Ollama dipendente dal download del modello
Il nuovo compose scarica automaticamente il modello alla prima esecuzione tramite `ollama-pull`.

Effetto:
- il primo `docker compose up --build` può richiedere tempo perché deve scaricare il modello
- se `OLLAMA_MODEL` viene cambiato, il pull deve essere rifatto

### Rischio 3: ticket plugin demo-only
`TicketApertiPlugin` contiene dati hardcoded e risponde con ticket statici.

Effetto:
- utile per demo/test, ma non rappresenta un backend reale
- rischio di aspettative sbagliate se il progetto viene letto come integrazione operativa

### Rischio 4: heuristic di routing molto semplice
La logica di `SemanticKernelOpenAIChatGateway` attiva il routing ticket quando il messaggio utente contiene la parola `ticket`.

Effetto:
- può attivare tool anche quando non serve
- non copre sinonimi o richieste operative senza la parola chiave

### Rischio 5: XTTS in modalità CPU
Il servizio XTTS nel compose usa l'immagine CPU compatibile per evitare dipendenze NVIDIA sul host corrente.

Effetto:
- il compose parte anche su host senza GPU NVIDIA
- se serve la variante GPU, va introdotto un override dedicato separato


## 5) Riepilogo operativo

- **Stato**: il backend stack è ora riproducibile con Docker Compose
- **Servizio .NET**: presente, compilato, esposto su porta 5077 nel compose
- **Ollama**: aggiunto come upstream locale con pull automatico del modello
- **XTTS**: incluso nel compose in versione CPU compatibile; la variante GPU richiede override separato
- **Langfuse**: stack self-hosted incluso e tracing attivo sui bot Pipecat e sul servizio .NET, con chiavi centralizzate in `.env`

- **Client Python**: presenti e usabili, ma senza packaging dichiarato
- **Priorità consigliata**: 1) packaging Python completo, 2) profilo XTTS CPU opzionale, 3) test minimi

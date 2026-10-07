# MacTitan

MacTitan is a macro research assistant for traders of Bitget rTokens. rTokens are Bitget's spot-traded tokens that track US-listed equities and ETFs, quoted in USDT (rAAPL, rNVDA, rSPY, and similar). You ask a question in plain language ("How does rNVDA usually react to CPI?", "Which sectors move most around FOMC decisions?", "When is the next jobs report?") and the answer is built from real, computed numbers: maintained official event calendars, daily price history from Bitget's spot market, category-level CPI data from the Bureau of Labor Statistics, and live feeds from the Federal Reserve and the White House.

**Web:** https://mactitan.useomniagents.xyz  |  **Telegram:** https://t.me/mactitan_bot  |  **License:** MIT

## The questions it answers

Seven tools cover the product's full scope. The language model maps a free-form question onto them; every number in an answer comes from one of these executions.

| Ask about | Tool | Data behind it |
|---|---|---|
| How a token reacts to a macro event | `get_event_reaction` | 19 event calendars and daily candles |
| Which sectors are most sensitive to an event | `get_sector_sensitivity` | scan of the 116-token universe |
| Whether a token's volatility is elevated right now | `get_current_volatility` | last 60 daily closes |
| When an indicator is released next | `get_upcoming_event` | maintained official calendars |
| What is driving the latest CPI print | `get_cpi_breakdown` | BLS component series |
| What Fed officials have said recently | `get_recent_fed_speeches` | Fed speeches RSS, live |
| What is on the White House schedule | `get_potus_schedule` | cached ICS window, refreshed every 10 minutes |

## How an answer is produced

One request cycle: standard function calling with deterministic computation in the middle.

```
question
  -> the model picks a tool and arguments
  -> Python executes the tool against real data
  -> the tool returns computed numbers
  -> the model explains those numbers in plain language
  -> answer, tools used, conversation history
```

The computation layer is ordinary Python and NumPy, executed per request. The model never supplies a number itself. If a tool errors or comes back empty, that is exactly what the answer reports.

## Data sources

Every dated fact in an answer traces to one of six sources. Each was tested against live behavior, and the measured quirks are documented here because they shaped the design.

### The event calendar (data/macro_calendar.py)

Coverage: 19 US macro event types. Fifteen carry the issuing agency's official 2026 schedule, taken from the agency's own calendar page: FOMC (federalreserve.gov), CPI, PPI, nonfarm payrolls, unemployment, JOLTS (bls.gov), PCE and GDP (bea.gov), retail sales, durable goods orders, housing starts, trade balance (census.gov), industrial production (Fed G.17), and University of Michigan consumer sentiment, preliminary and final (the UMich survey's own schedule).

Four are computed from a fixed institutional rule the agency confirms: ISM Manufacturing on the first business day of the month, ISM Services on the third, initial jobless claims every Thursday, and Conference Board consumer confidence on the last Tuesday. Computed dates are cross-checked against real releases, and known exceptions are handled explicitly. Example from 2026: the first-business-day rule lands on January 1 for ISM Manufacturing, a holiday; the real date, January 5, is recorded as an explicit override.

Why a maintained file rather than an API lookup: the agencies publish these schedules months ahead on their own pages, so the file is exact, answers instantly, and depends on no third service at question time. Maintenance is an annual pass over each agency's schedule page; the source URLs sit at the top of the file.

### FRED (core/macro_data.py): values only

FRED, the St. Louis Fed's public API, supplies series values, primarily CPIAUCSL. Two behaviors, both found by live testing, bound what this integration is allowed to do:

1. FRED's `realtime_start` field is unreliable as a publication date for revision-prone series. When CPI receives a seasonal-adjustment revision, several reference months come back stamped with the same revision date; in testing, three different reference months returned one identical "release date". Values therefore come from FRED and dates come from the maintained calendar, joined by reference month.
2. FEDFUNDS is the effective (market-traded) federal funds rate and drifts slightly between meetings. Reading month-over-month changes to detect policy decisions flagged a 0.01 point move as a "cut" in testing. Decision dates come from the Fed's published meeting calendar instead, and the inference function is kept in the code marked deprecated so nobody re-derives that mistake.

FRED's release-dates endpoint was also tested and does not reliably return forward-looking dates, so "when is the next release" never depends on it.

### BLS public API (core/bls_data.py)

Category detail that a headline series does not carry. Curated, seasonally adjusted CPI components: CUSR0000SA0 (headline), CUSR0000SA0L1E (core), CUSR0000SAF1 (food), CUSR0000SA0E (energy), CUSR0000SAH1 (shelter), plus CES0000000001 (total nonfarm employment). Annual-average marker months (M13) are filtered out.

The BLS API does not expose release dates, so components are joined to dates by reference period. The join is exact: headline CPI and its component breakdown ship in the same report on the same day, so a component month maps to that month's confirmed calendar date. Months without a confirmed date are skipped rather than approximated.

### Bitget market data (core/price_fetch.py, core/holdings_fetch.py)

Price history comes from Bitget's public v2 candle endpoint (api.bitget.com/api/v2/spot/market/candles), shared infrastructure for all users. rToken tickers map straight to symbols (rAAPL becomes RAAPLUSDT). Candles arrive newest-first and are reversed once at the boundary so every downstream function works oldest-first.

Private portfolio features read the account assets endpoint with HMAC-SHA256 request signing and read-only keys. Holdings are filtered to base coins with the r prefix, and quantities include frozen amounts.

### Fed speeches (core/fed_speeches.py), live

The Fed publishes speeches as RSS at federalreserve.gov/feeds/speeches.xml. The feed carries a rolling window of roughly the 20 most recent items. Speakers are identified by matching known official names in titles and summaries, and dates are normalized from RFC 2822 to ISO. The scope is stated inside the tool's own result payload so the model can repeat it plainly: the feed shows what has been published, and individual speeches are not scheduled months ahead the way CPI is.

### White House schedule (core/potus_schedule.py), live

Sourced from Factba.se / Roll Call, which republishes the day-of White House schedule as a public Google Calendar in ICS form. Measured against the real file: about 10.9 MB, roughly 34 seconds to first byte, about 90 seconds end to end.

That profile dictates the design. A background thread refreshes a cache every 10 minutes (retrying after 2 minutes on failure) and stores the useful slice, from 2 days back to 14 days ahead, in potus_cache.json. The file is streamed and parsed line by line, so the parser's footprint stays small, sized for a 512 MB instance. The refresh thread starts when the application starts, so the initial 1 to 2 minute download happens before the first question. The chat tool reads only the cache and answers in milliseconds; it never downloads inside a request. Cached data older than 3 hours is refused rather than shown, because a stale day-of schedule misleads.

Parsing limitations, stated where they are known: recurring events (RRULE) are counted but not expanded, entries without a time zone are assumed UTC, and all-day entries are skipped. The source is third-party journalism, and the tool's result says so.

## The measurement layer

Pure functions, no network inside them. Prices are fetched once per request and passed in, which keeps every computation injectable and checkable against synthetic series.

### Event reactions (core/event_reaction.py)

For one ticker and one event type, each event date contributes one reaction:

- Pre-event price: the nearest available trading day strictly before the event date. The strict comparison matters; if the event day could match itself, a token that gapped on the day would report a zero move.
- Post-event price: the nearest available trading day on or after the event date plus 3 days.
- Move: percent change between the two.
- Realized volatility: standard deviation of daily returns from the event day through the post day. The window starts at the event deliberately; starting it one day earlier would dilute the measure with pre-event calm.

Events outside a token's available history are skipped (rTokens are young; 100 daily candles is the working window), and the summary reports how many events were usable out of how many were asked. Summaries carry the average move, the average realized volatility, and direction consistency: "up" or "down" when at least 70 percent of events move the same way, otherwise "mixed".

### Sector sensitivity (core/sector_sensitivity.py)

The full mapped universe (116 tokens across 13 sector groups) is scanned per event type. Each token's reactions are summarized, then sectors are ranked by average absolute move, the measure that captures "how much it moves" in either direction. A single dead or delisted symbol must not end the scan, so per-token failures are isolated and skipped, and the ranking reports how many tokens each sector's figure rests on.

### Volatility regime (core/stats.py)

60 daily closes: the last 10 days against everything before them, recent realized volatility measured against the token's own baseline. "Elevated" means a ratio of at least 1.5x, a threshold chosen because it is explainable in an answer. When history is too short for a meaningful comparison, the tool returns nulls instead of a number computed from a sample too small to trust.

### Portfolio structure (core/portfolio.py)

Beta against rSPY (covariance over variance on daily returns), pairwise Pearson correlations, sector weights, and value-weighted portfolio beta. Two engines:

- Evaluate a holdings set and optionally recompute the same snapshot with a candidate trade added, so "what happens if I add rXOM" is measured on the same data as the current book.
- Rank tokens the portfolio does not hold by their average correlation to what it does hold, lowest first, as diversification candidates.

## Answer integrity

The trust rules are enforced in code and restated in the system prompt:

- Tool errors propagate as errors. The model sees the error text and repeats it rather than inventing a recovery.
- Unknown tool names, unknown event types, and empty results come back as explicit error payloads.
- Volatility on too little history returns nulls.
- The two live feeds attach scope notes to their own results, covering what they cannot answer.
- A stale cache is refused rather than displayed.
- The system prompt forbids supplying numbers from memory and forbids filling gaps. It also sets the tone: direct, grounded in the numbers returned, no generic disclaimers.

## Language interface

One core conversation function (core/assistant.py) sits behind two transports:

- Web (POST /chat): stateless. The frontend owns the conversation, sends the full history with each message, and receives the updated history in the response. A refresh or a redeploy loses nothing because the client can replay its own history.
- Telegram (POST /telegram/webhook): the server owns the conversation. Per-chat history is persisted in a local SQLite file so it survives restarts and redeploys, which a Telegram client cannot manage on its own. Single-instance by design; the storage module documents the migration path (a shared store) if this ever runs on more than one instance.

How the model is made to talk:

- Answers state what the data shows. Generic disclaimers and excessive hedging are instructed away.
- When a tool errors or returns nothing usable, the answer says so instead of filling the gap.
- Scope limits are part of the vocabulary. The prompt directs the model to say plainly that the two live feeds show what is published today, and never to imply that next month's speeches or White House schedule can be listed.
- Event types follow the trader's vocabulary: "nonfarm payrolls" and "unemployment" both resolve to the same real release, because they are the same report.
- History is returned by every request and passed back in, on both transports, so follow-ups like "and what about rTSLA?" inherit the context of the earlier tool results.

Formatting is generated once and adapted per transport. The model always produces full markdown. The web frontend renders it as-is (marked.js) with Chart.js for the charts. Telegram has no table rendering, so core/telegram_format.py reflows markdown tables into plain "Label: value" lines after generation; a leading purely numeric column (a rank) is promoted so lines read "Technology, Avg Abs Move: 1.69%" rather than "1, Sector: ...". If Telegram's Markdown parse rejects a message, the send is retried as plain text.

## HTTP API

The backend exposes three endpoints. End users reach them through the web app and Telegram, which talk to the deployment on the user's behalf; the section documents the contract for anyone building on the same backend.

| Endpoint | Purpose |
|---|---|
| `GET /health` | liveness check |
| `POST /chat` | web conversation |
| `POST /telegram/webhook` | Telegram updates |

`POST /chat` request body:

```json
{"message": "How does rNVDA usually react to CPI?", "history": []}
```

Response:

```json
{
  "answer": "...",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
  "tools_used": ["get_event_reaction"],
  "tool_results": [{"tool": "get_event_reaction", "args": {}, "result": {}}]
}
```

`tool_results` is exposed deliberately, so a client can show what an answer is based on. CORS is restricted to the product origin and localhost development ports.

## Configuration

Environment variables, read at startup (see .env.example):

| Variable | Used for |
|---|---|
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | the model backend. Any OpenAI-compatible chat endpoint works (Bitget's hackathon Qwen gateway, DeepSeek, Groq, OpenAI, and others). Switching providers is an environment change, no code. |
| `FRED_API_KEY` | free registration key from the St. Louis Fed |
| `BLS_API_KEY` | BLS public API registration key |
| `BITGET_API_KEY`, `BITGET_API_SECRET`, `BITGET_API_PASSPHRASE` | read-only keys, used only by the private holdings features |
| `TELEGRAM_BOT_TOKEN` | the Telegram transport |

## Verification

Three test scripts, all against live services, no mocks. The product's correctness claim is "real data, real computation", and only live checks prove it:

- tests/integration_test.py exercises every tool's computation directly: candles, FRED series, the BLS join, event reactions, sector rankings, volatility, calendar lookups. The output is real numbers meant to be read by a person before trusting the model layer on top.
- tests/test_assistant.py runs real questions end to end through the model and reports which tools fired per question.
- tests/test_live_feeds.py fetches the Fed RSS feed and performs the full White House schedule download, the two paths with real network behavior worth verifying.

## Known limitations

The assistant states the scope of its data in its own answers, so each of the following surfaces in an answer when it applies:

- Every figure rests on real traded history. Event studies cover the events inside each token's listing lifetime, sized to the 100 daily candles of the working window, and each summary reports exactly how many events contributed to its figures.
- The universe map covers 116 liquid, well-known tokens, each checked against Bitget's live instruments endpoint before being added; unmapped symbols are labeled Unknown.
- Reactions are measured against the event date itself, on data that is entirely free and public. Answers speak in realized moves, a framing anyone can reproduce from the same agency sources.
- Calendar dates follow the agencies' own institutional rules. Rule-computed dates (ISM, jobless claims, consumer confidence) are cross-checked against real releases, confirmed agency schedules take precedence, and known holiday conflicts are recorded as explicit overrides, such as ISM Manufacturing on January 5 in 2026.
- The two live feeds mirror what their publishers publish: the Fed speeches feed carries its recent window, and the White House schedule arrives day-of from its journalistic source. The assistant states this scope plainly.
- Telegram conversation history lives in a per-chat SQLite file, a self-contained choice that fits the single-instance deployment, with a documented migration path to a shared store if the deployment ever scales out.

## Repository layout

```
main.py                  FastAPI app: /chat, /telegram/webhook, startup jobs
core/
  assistant.py           orchestration: model, tools, answer
  llm_client.py          OpenAI-compatible client, provider set by env
  tools.py               the 7 tool functions and their schemas
  event_reaction.py      event-window measurement
  sector_sensitivity.py  universe scan and sector ranking
  stats.py               returns, beta, correlation, volatility
  portfolio.py           holdings evaluation and diversifier ranking
  price_fetch.py         Bitget public candles
  holdings_fetch.py      Bitget signed account assets
  macro_data.py          FRED values
  bls_data.py            BLS CPI components and the release-date join
  fed_speeches.py        Fed speeches RSS
  potus_schedule.py      White House ICS, background cache
  telegram_format.py     markdown tables to Telegram-safe lines
  chat_storage.py        SQLite per-chat history
data/
  macro_calendar.py      the 19 event calendars, sourced and dated
  sector_map.py          116 tokens, 13 sector groups, rSPY benchmark
web/                     static frontend: landing, chat, charts
tests/                   the three live verification scripts
```

## Contributing

Issues and pull requests are welcome. Changes to measurement code or calendar data should come with the corresponding verification script output against live endpoints, so reviewers can check the numbers directly. Useful directions: extending the universe map, adding indicators with their agency rules, and hardening the live feed parsers.

## License

MIT. See [LICENSE](LICENSE).


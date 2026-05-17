# @anoromi/local-ai-tools-protocol

Effect Schema definitions and JSON line helpers for `local-ai-tools` clients.

This package contains only the reusable protocol surface:

- daemon Unix-socket request/response schemas
- daemon streaming event schemas
- session NDJSON request/event schemas
- TypeScript types inferred from the schemas
- encode/decode helpers for JSON lines

It does not include a socket client, daemon auto-start logic, filesystem path
resolution, or CLI code.

## Install

```bash
npm install @anoromi/local-ai-tools-protocol effect@4.0.0-beta.45
```

## Usage

```ts
import {
  decodeDaemonLine,
  decodeSessionLine,
  eventLine,
  requestLine,
} from "@anoromi/local-ai-tools-protocol"

const request = decodeSessionLine(
  '{"id":"1","method":"health","params":{}}'
)

const daemonLine = requestLine("2", "health", {})

const event = eventLine({ event: "ready", version: "0.1.0" })

const daemonResponse = decodeDaemonLine(
  '{"id":"2","ok":true,"result":{"status":"ok"}}'
)
```

## Session NDJSON

```json
{"id":"1","method":"synthesize","params":{"text":"Hello","output_path":"/tmp/hello.wav","timings_path":"/tmp/hello.json","voice":"af_sarah","speed":1,"target_wpm":null,"format":"wav"}}
```

Selection requests use one shared text and many question items:

```json
{"id":"2","method":"select","params":{"text":"The deploy passed. The parser failed.","items":[{"id":"failures","question":"What failed?","threshold":0.5}],"language":"auto","include_all_scores":false}}
```

Classification requests use many sentences and many labels:

```json
{"id":"3","method":"classify","params":{"sentences":[{"id":"s1","text":"The deploy passed."},{"id":"s2","text":"The parser failed."}],"labels":[{"id":"success","label":"success","threshold":0.5},{"id":"issue","label":"issue","threshold":0.5}],"hypothesis_template":"This sentence indicates {}.","include_all_scores":false}}
```

Common session events:

```json
{"event":"ready","version":"0.1.0"}
{"id":"1","event":"accepted"}
{"id":"1","event":"started"}
{"id":"1","event":"chunk","chunk":{"index":0,"text":"Hello","start":0,"end":1.2,"duration":1.2,"timing_basis":"native"}}
{"id":"1","event":"finished","result":{"output_path":"/tmp/hello.wav","timings_path":"/tmp/hello.json"}}
```

## Compatibility

This package uses Effect 4 schemas and declares `effect@4.0.0-beta.45` as a peer
dependency.

Generated `dist/` files are produced during package build and publish. They are
not committed in the `local-ai-tools` monorepo.

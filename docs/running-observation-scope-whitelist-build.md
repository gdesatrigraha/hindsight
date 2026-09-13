# Run the observation-scope whitelist build

This guide runs the Hindsight API and coding-agent integration from this repository checkout. Do
not use the published Hindsight container or clients for this feature: those artifacts may not
contain the bank-level `observation_scope_tag_key_whitelist` policy yet.

The commands below assume the repository is checked out on a branch containing this feature.

## Prerequisites

- Git.
- For the recommended API path: Docker with at least 8 GB of free memory.
- For a direct source run: Python 3.11 and [`uv`](https://docs.astral.sh/uv/).
- For the Control Plane and coding-agent integration: Node.js 24 LTS is recommended. Devin CLI
  needs Node 22.5 or newer, and DeepSeek Harness session import needs Node 22.15 or newer.
- An API key for the configured LLM provider. The examples use OpenAI.

Never commit API keys. Export them only in the shell that starts Hindsight:

```bash
export HINDSIGHT_API_LLM_API_KEY="your-api-key"
```

## 1. Get this build

```bash
git clone <repository-url> hindsight
cd hindsight
git switch <branch-containing-this-feature>
```

If the repository already exists locally:

```bash
git fetch origin
git switch <branch-containing-this-feature>
git pull --ff-only
```

## 2. Run the API

### Option A: build an API-only Docker image (recommended)

Run the build from the repository root. The `api-only` target contains the API from this checkout
without the control-plane UI.

```bash
docker build \
  --file docker/standalone/Dockerfile \
  --target api-only \
  --tag hindsight-api:observation-scope-whitelist \
  .
```

The default build includes and preloads the local embedding and reranking models. This makes the
image larger, but the running API only needs the LLM provider configuration.

Use a named Docker volume for the embedded PostgreSQL data. A named volume avoids host-directory
ownership problems because the container runs as an unprivileged user.

```bash
docker volume create hindsight-observation-scope-data

docker run --detach \
  --name hindsight-observation-scope \
  --restart unless-stopped \
  --publish 8888:8888 \
  --env HINDSIGHT_API_LLM_PROVIDER=openai \
  --env HINDSIGHT_API_LLM_API_KEY \
  --env HINDSIGHT_API_LLM_MODEL=gpt-4o-mini \
  --volume hindsight-observation-scope-data:/home/hindsight/.pg0 \
  hindsight-api:observation-scope-whitelist
```

Watch startup and verify health:

```bash
docker logs --follow hindsight-observation-scope
curl --fail http://localhost:8888/health
```

The first startup can take several minutes while models initialize. Press `Ctrl-C` to stop
following the logs; the container continues running.

Common lifecycle commands:

```bash
docker stop --time 30 hindsight-observation-scope
docker start hindsight-observation-scope
docker logs --tail 200 hindsight-observation-scope
```

To rebuild after pulling changes, stop and replace the container but keep the named volume:

```bash
docker stop --time 30 hindsight-observation-scope
docker rm hindsight-observation-scope

docker build \
  --file docker/standalone/Dockerfile \
  --target api-only \
  --tag hindsight-api:observation-scope-whitelist \
  .
```

Then repeat the earlier `docker run` command. Removing the container does not remove the named
volume. Do not delete `hindsight-observation-scope-data` unless the stored memory can be discarded.

### Option B: run directly from the checkout

From the repository root, create the local environment file and install the workspace package. The
`hindsight-api` meta-package includes the embedded-database and local-model dependencies:

```bash
cp .env.example .env
uv sync --locked --package hindsight-api
```

Edit `.env` and set at least the LLM provider, key, and model:

```dotenv
HINDSIGHT_API_LLM_PROVIDER=openai
HINDSIGHT_API_LLM_API_KEY=your-api-key
HINDSIGHT_API_LLM_MODEL=gpt-4o-mini
```

Start the checked-out API with the repository's development script:

```bash
./scripts/dev/start-api.sh
```

The API listens on `http://localhost:8888` by default and uses embedded PostgreSQL when
`HINDSIGHT_API_DATABASE_URL` is unset. Stop it with `Ctrl-C`.

For automatic reloads while editing server code, use:

```bash
./scripts/dev/start-api.sh --reload
```

## 3. Run and configure the Control Plane

The recommended Docker image above contains only the API. Run the Control Plane separately from
this checkout so that it includes the whitelist editor added by this feature.

From the repository root, install the JavaScript workspace dependencies and start the UI:

```bash
npm ci
./scripts/dev/start-control-plane.sh
```

The startup script builds the local TypeScript client before starting the Control Plane. By default,
the UI listens on `http://localhost:9999` and connects to the API at `http://localhost:8888`. To use
a different API URL, set `HINDSIGHT_CP_DATAPLANE_API_URL` before starting it.

Open `http://localhost:9999`, then:

1. Create or select the memory bank whose observation policy you want to configure. For the API
   smoke test below, use `whitelist-demo`. For the coding-agent example later in this guide, use
   `shared-engineering-bank`; configuration is isolated per bank.
2. Open **Bank Configuration** and find the **Observations** section.
3. Under **Observation Scope Tag-Key Whitelist**, choose **Custom**.
4. Add each permitted tag key, such as `project` and `user`, then save the Observations section.

The editor preserves all three policy states:

- **Server Default** leaves the bank override unset and preserves legacy or inherited behavior.
- **Custom** with no keys saves an explicit empty list, so no tagged observation dimensions are
  permitted and preset strategies use the shared scope `[[]]`.
- **Custom** with keys permits only those tag keys to participate in tagged observation scopes.

This setting filters observation scopes only. It does not remove provenance or other tags from
stored facts.

## 4. Smoke-test the bank policy

Create the bank and configure which tag keys may participate in observation scopes:

```bash
curl --fail-with-body \
  --request PUT \
  --header 'Content-Type: application/json' \
  --data '{
    "name": "Whitelist demo",
    "observation_scope_tag_key_whitelist": ["project", "user"]
  }' \
  http://localhost:8888/v1/default/banks/whitelist-demo
```

The retain request uses the ordinary observation strategy. It stores all four tags on extracted
facts, while only `project:*` and `user:*` tags are eligible for `combined`:

```bash
curl --fail-with-body \
  --request POST \
  --header 'Content-Type: application/json' \
  --data '{
    "items": [
      {
        "content": "The deployment workflow uses canary releases.",
        "tags": ["project:example", "user:developer", "source:chat", "harness:codex"],
        "observation_scopes": "combined"
      }
    ]
  }' \
  http://localhost:8888/v1/default/banks/whitelist-demo/memories
```

An explicitly empty whitelist, or one that matches no fact tags, creates the concrete shared scope
`[[]]`. It does not remove tags from the stored fact.

A successful response confirms that Retain uses the bank policy without needing to know its value.
Verifying generated observation scopes requires consolidation to run and is not immediate; inspect
the bank through the API or Control Plane after the retained facts have been consolidated.

## 5. Build and install the coding-agent integration

The published command
`npx @vectorize-io/hindsight-coding-agents ...` may install the official package rather than this
checkout. Build and invoke the local installer instead:

```bash
cd hindsight-integrations/coding-agents
npm ci
npm run skill:build
npm run build
```

Install one harness and point it at the API started above. For example, Codex CLI:

```bash
node ./dist/installer.js install codex \
  --server self-hosted \
  --api-url http://localhost:8888
```

Other supported harness names are:

```text
opencode
kilo
prime-agent
claude-code
codex
antigravity-cli
devin-cli
cursor-cli
copilot-cli
grok-build
cline-cli
dsh
```

`agy` is an alias for `antigravity-cli`. Multiple names can be supplied to one install command, or
use `install all` to install every detected harness:

```bash
node ./dist/installer.js install claude-code codex cursor-cli \
  --server self-hosted \
  --api-url http://localhost:8888

node ./dist/installer.js install all \
  --server self-hosted \
  --api-url http://localhost:8888
```

A bare `install` intentionally changes nothing. The installer copies this checkout's built runtime
to `~/.hindsight/coding-agents`, so installed hooks do not depend on the repository remaining at its
current path.

## 6. Configure observation scopes for coding agents

The default configuration file is:

```text
~/.hindsight/coding-agent.json
```

If `HINDSIGHT_CONFIG` is set, its value replaces this default path. Edit the file selected by that
environment variable instead.

The installer creates or updates its server fields. Add the observation configuration while
preserving any other settings already in the file:

```json
{
  "serverMode": "self-hosted",
  "apiUrl": "http://localhost:8888",
  "bankId": "shared-engineering-bank",
  "retainTags": ["project:{gitProject}"],
  "observationScopes": "all_combinations"
}
```

The coding-agent integration sends the normal `observationScopes` strategy and its provenance tags.
It does not independently filter tag keys and does not need to know the bank whitelist. Configure
the policy once on `shared-engineering-bank` through the bank configuration API, CLI, or Control
Plane. Existing `shared`, `combined`, `per_tag`, and `all_combinations` behavior is unchanged when
the bank policy is unset.

Hook-based harnesses read the new configuration on their next prompt. Restart persistent plugin
harnesses, and start a new session for MCP-backed tools, after changing the configuration.

## 7. Update or uninstall the integration

After pulling a newer version of this branch, rebuild and rerun the same install command. Installation
is idempotent and recopies the runtime in place:

```bash
cd hindsight-integrations/coding-agents
npm ci
npm run skill:build
npm run build
node ./dist/installer.js install codex \
  --server self-hosted \
  --api-url http://localhost:8888
```

Uninstall only the wiring added for a harness with:

```bash
node ./dist/installer.js uninstall codex
```

Use `uninstall all` to remove this integration from every detected harness. The installer preserves
unrelated harness configuration and writes a backup before changing an existing configuration file.

## Troubleshooting

- **The API does not expose the whitelist field:** confirm the container was built from this checkout
  and is using `hindsight-api:observation-scope-whitelist`, not the published image.
- **The harness sends requests to Hindsight Cloud:** rerun the local installer with
  `--server self-hosted --api-url http://localhost:8888`, then inspect
  `~/.hindsight/coding-agent.json`.
- **The harness still uses old code:** rerun `npm run build` and the same local install command; the
  installer must recopy the rebuilt runtime.
- **The API is unreachable from a containerized harness:** `localhost` refers to that harness
  container. Use a network-reachable host name such as `host.docker.internal` where supported.
- **A whitelist produces shared observations:** this is expected when the whitelist is empty or no
  retained tag has a matching key; the concrete scope is `[[]]`.

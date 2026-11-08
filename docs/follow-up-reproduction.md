# Reproducing the follow-up studies

The follow-up runner supports two separate plans: 24 positive Office cases plus six negative controls, and nine positive GnuCash cases. The [methodology](robustness-methodology.md) defines their inputs, geometry and outcome checks. These commands create new evidence; they do not imply that either plan has completed or passed.

## Prepare a fresh checkout

Use a fresh source checkout of the committed revision you intend to measure. Requirements are Python 3.11 or newer, Docker with Compose v2, and an OpenAI API account with access to the configured model. The recorded environment is a Linux arm64/X11 guest with a 1200×900 display; the freeze helper describes that architecture explicitly. Use an arm64 Docker environment for this protocol. Other architectures require a separately documented protocol rather than being labelled as the same environment.

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
mkdir -p output
docker compose build desktop
```

Add your API key to the local `.env` file before execution. Keep that file private. Plan generation and packaging make no model calls. Building the image needs package-download access; the desktop used for each attempt is isolated from the network. The study CLI acquires the shared desktop lock for execution; plan-only inspection does not need that lock. Allow only one study or other desktop command to run at a time, and do not send manual inputs during measured attempts.

The original frozen setup used source revision `7f269cd03b47dd83b62ca77a2aefba4b6058bf51` and image ID `sha256:9a83a615fe1441b1e88e7f7f7f04af52aa454b9223c2a14cb11bf2bb3f7c46d9`. A new reproduction has its own recorded revision, image ID, installed application versions and host details. Even rebuilding the same commit can produce a different image because system package versions can change. Do not copy a published freeze context into changed code or relabel a new image with the original identity.

## Freeze both new contexts and inspect the plans

By default, the freeze helper writes new contexts under `output/`:

```bash
python -m scripts.freeze_followup_studies
```

It checks that the measured source/configuration files exactly match their committed `HEAD` versions, inspects the built `ledgerdesk-demo:local` image and application versions, and writes:

- `output/office-freeze-context.json`
- `output/gnucash-freeze-context.json`

It refuses to overwrite either existing context. Use `--output-dir output/another-freeze` to create a separately named pair of contexts without changing earlier freezes; pass the corresponding new paths to the runner. Use a fresh checkout for a new reproduction; preserve earlier contexts and evidence. Commit any intended runtime changes before freezing, then keep the measured code, model, instructions, fixtures and image unchanged throughout both plans. The helper fixes the requested API model identifier to `gpt-6.1-terra` with medium reasoning; no immutable provider-weight snapshot is verified, and provider-side changes remain outside the study’s control; the study CLI does not offer a model override.

Create the two campaign directories without executing an attempt:

```bash
python -m scripts.run_robustness_study \
  --context output/office-freeze-context.json \
  --study-dir output/office-reproduction \
  --plan-only

python -m scripts.run_robustness_study \
  --context output/gnucash-freeze-context.json \
  --study-dir output/gnucash-reproduction \
  --limit 9 \
  --plan-only
```

Inspect each directory's `protocol.json` and `status.json`. `--plan-only` freezes the protocol, input/instruction/expected-result hashes, limits and shuffled case order, but sends no API request and starts no measured desktop attempt. The random seed is fixed at `20261108`; it is not a CLI option. Office files and instructions are identical within each normal/changed geometry pair. Controls are listed separately from positive tasks.

## Execute and continue

Run the campaigns sequentially:

```bash
python -m scripts.run_robustness_study \
  --context output/office-freeze-context.json \
  --study-dir output/office-reproduction \
  --limit 30

python -m scripts.run_robustness_study \
  --context output/gnucash-freeze-context.json \
  --study-dir output/gnucash-reproduction \
  --limit 9
```

`--limit` is a cumulative attempt-slot limit, not a retry count. To inspect a first slice, use `--limit 1`, then rerun the same command and context with a larger limit. For example, moving Office from 1 to 30 executes only its remaining slots. There is no separate `--resume` flag. Finished successes, failures and unverified slots are retained, never replaced.

Each attempt starts from a fresh guest. The runner appends a durable `started` event before execution and a `finished` event afterward to the campaign's `events.jsonl`. It writes per-attempt evidence under `output/runs/`, with references from the campaign ledger. Preserve both the campaign directory and its referenced run directories.

If the process stops after a start event without a finish event, the next execution records that slot as unverified with unknown cost, then stops for inspection. A later invocation can continue the remaining slots; it does not replay the interrupted one. Returned runner errors, environment drift and certain provider errors also stop the campaign for inspection. Do not repair the ledger, delete a failure or alter the context to make it continue. A source, fixture, prompt, model or image change belongs in a new study.

The per-attempt limits are USD 1 estimated model cost, 30 requests, 80 inputs and 420 seconds of agent-loop time. Campaign allowances are USD 20 for Office and USD 10 for GnuCash. These fixed local guards are not provider billing caps; setup, verification and teardown are outside the agent time guard. Unknown usage reserves the full per-attempt budget rather than counting as zero. A partial run can exit with status 1 intentionally; inspect `status.json` and the ledger to distinguish the limit, budget, failure and interruption cases. A fully finished plan with failed or unverified grades also exits 1.

## Recheck and package new evidence

After every planned slot has a finish record, package from the same unchanged checkout into new, empty destinations outside the study and run directories:

```bash
python -m scripts.package_followup_study \
  --study-dir output/office-reproduction \
  --destination output/packages/office-reproduction

python -m scripts.package_followup_study \
  --study-dir output/gnucash-reproduction \
  --destination output/packages/gnucash-reproduction
```

The offline packager checks the frozen plan, retained source hashes, original execution grades and saved outputs or control evidence. It retains failures and missing evidence; a correct saved artifact cannot upgrade a failed original execution. It copies an allowlist of raw evidence without rewriting it and creates `summary.json`, `recheck.json`, `index.html` and a SHA-256 `manifest.json`. Nonempty destinations and symlink escapes are rejected.

Positive task metrics and expected control refusals remain separate. Cost per verified success includes failed positive attempts with complete usage; incomplete cost or outcomes leave it unavailable. Operator-intervention counts, paired geometry differences and missing measurements remain explicit. The missing-source control's offline check establishes consistency of its recorded preflight evidence, not a new live observation of the old guest.

Keep these new packages separate from the original `examples/` archives. Do not edit an immutable package to add a new run or replace an outcome. Review the new evidence and its scope before choosing whether to publish it.

The supported runner flags are `--context`, `--study-dir`, `--limit` and `--plan-only`. The packager accepts `--study-dir` and `--destination`; both expose `--help`. The freeze helper accepts `--output-dir` and `--help`. There are no study CLI flags for retries, model selection, seed, per-attempt limits or campaign budget.

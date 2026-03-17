# OpenALP MVP

OpenALP is an **Open Agentic Language Protocol** prototype focused on machine-to-machine execution.

## Why Open Agentic Language Protocol is needed

Current agent ecosystems rely heavily on natural-language prompts as an execution medium. That causes:

1. high translation overhead from text to actions,
2. non-deterministic interpretation across agent stacks,
3. weak interoperability between foreign agent runtimes,
4. trust and reproducibility gaps.

OpenALP addresses this with machine-first artifacts (`.alp`, `.alpb`), deterministic execution, and verifiable exchange bundles.

## What OpenALP provides

1. Portable executable format: `.alp`
2. Raw low-level authoring format: `.alpb`
3. Deterministic stack runtime
4. Validation + checksum + signature gates
5. Capability negotiation (`ALP-Hello`)
6. Browser demos for quick evaluation

## Public Launch Assets

- Landing page: `web/landing.html`
- Browser runner: `web/index.html`
- OpenALP-rendered webpage: `web/alp_site.html`
- Agent context: `docs/AGENT_CONTEXT.md`
- Interop pack: `docs/INTEROP_PACK.md`
- Install guide: `INSTALL.md`
- Licensing details: `docs/LICENSING.md`
- Git publication guide: `docs/GIT_PUBLICATION.md`
- Release notes: `docs/RELEASE_NOTES_V0_1_0_MVP.md`
- Changelog: `CHANGELOG.md`
- License: `LICENSE`

## Quick Start

```bash
cd alp_mvp
./scripts/setup.sh
export PYTHONPATH="$PWD"
python3 -m alp.cli run samples/hello.alp
```

## Full CLI Smoke Sequence

```bash
export PYTHONPATH="$PWD"
python3 -m alp.cli validate samples/add.alp
python3 -m alp.cli run samples/add.alp
python3 -m alp.cli build-raw samples/hello.alpb samples/hello_from_raw.alp
python3 -m alp.cli run samples/hello_from_raw.alp
python3 -m alp.cli checksum verify samples/add.alp
python3 -m alp.cli sign verify samples/add.alp --key samples/dev_hmac.key
python3 -m alp.cli keygen-demo-rsa samples/demo_rsa
python3 -m alp.cli sign-rsa create samples/add.alp --key samples/demo_rsa.priv.json
python3 -m alp.cli sign-rsa verify samples/add.alp --key samples/demo_rsa.pub.json
python3 -m alp.cli determinism report samples/planner_loop.alp --runs 5
python3 -m alp.cli handshake validate samples/hello_ref_vm.json
./scripts/quality_gate.sh
./scripts/release_mvp.sh
```

## Browser Demos

Open directly in browser:

- `web/index.html` (run `.alpb` source in browser)
- `web/alp_site.html` (render HTML emitted by OpenALP program)
- `web/landing.html` (project landing)

## Reference Docs

- Spec: `spec/alp-v0.1.md`
- Onboarding: `docs/ONBOARDING.md`
- Agent context: `docs/AGENT_CONTEXT.md`

## Demo Sources

- Hello executable: `samples/hello.alp`
- Hello raw source: `samples/hello.alpb`
- Webpage raw source: `samples/webpage.alpb`

## Licensing Notice

This repository is **not open-source licensed**.
Usage requires explicit written permission from the repository owner. See `LICENSE` and `docs/LICENSING.md`.

# Git Publication Checklist

## Before Publishing

1. Run `./scripts/launch_check.sh`
2. Rebuild release artifact with `./scripts/release_mvp.sh`
3. Confirm `README.md`, `LICENSE`, and `docs/AGENT_CONTEXT.md` are present
4. Confirm browser landing page opens: `web/landing.html`

## Suggested Initial Public Release Assets

1. Source tree
2. `dist/openalp-v0.1.0-mvp.tar.gz`
3. Launch note linking:
- `README.md`
- `docs/ONBOARDING.md`
- `docs/AGENT_CONTEXT.md`
- `web/landing.html`

## Suggested Git Commands

```bash
git init
git add .
git commit -m "Release OpenALP v0.1.0-mvp"
# then create remote and push from your GitHub account
```

Network publication is intentionally a manual step so release ownership stays with the maintainer.

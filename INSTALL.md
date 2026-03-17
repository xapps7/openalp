# OpenALP Install

## Dependencies (MVP)

OpenALP MVP requires only:

1. Python 3.10+
2. OpenALP source tree or release bundle

No third-party Python packages are required.

## One-Command Setup

```bash
cd openalp
./scripts/setup.sh
```

## Manual Setup

```bash
cd openalp
export PYTHONPATH="$PWD"
python3 -m alp.cli validate samples/add.alp
python3 -m alp.cli run samples/hello.alp
```

## Release Bundle Setup

```bash
tar -xzf openalp-v0.1.1.tar.gz
cd openalp
./scripts/setup.sh
```

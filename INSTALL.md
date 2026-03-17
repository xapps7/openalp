# OpenALP Install

## Agent-First Quick Path (Preferred)

```bash
curl -L -o openalp-v0.1.1.tar.gz https://github.com/xapps7/openalp/releases/download/v0.1.1/openalp-v0.1.1.tar.gz
tar -xzf openalp-v0.1.1.tar.gz
cd openalp
./scripts/setup.sh
export PYTHONPATH="$PWD"
python3 -m alp.cli bundle run --bundle samples/add.alppb --key samples/dev_hmac.key
```

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

## CLI Install From Public Release

```bash
curl -L -o openalp-v0.1.1.tar.gz https://github.com/xapps7/openalp/releases/download/v0.1.1/openalp-v0.1.1.tar.gz
tar -xzf openalp-v0.1.1.tar.gz
cd openalp
./scripts/setup.sh
export PYTHONPATH="$PWD"
python3 -m alp.cli run samples/hello.alp
```

## CLI Install From Git

```bash
git clone https://github.com/xapps7/openalp.git
cd openalp
./scripts/setup.sh
export PYTHONPATH="$PWD"
python3 -m alp.cli run samples/hello.alp
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

## Verification

```bash
export PYTHONPATH="$PWD"
python3 -m alp.cli validate samples/add.alp
python3 -m alp.cli bundle run --bundle samples/add.alppb --key samples/dev_hmac.key
python3 -m alp.cli run samples/hello.alp
./scripts/launch_check.sh
```

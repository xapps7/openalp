# OpenALP Governance v0.2

## Scope

This document defines protocol governance rules for OpenALP runtime and bundle exchange.

## Machine-Enforced Fields

1. `protocol` must be `ALP`
2. `protocol_version` must be one of:
   - `0.1`
   - `0.2`
3. `module_version` must be compatible with the declared `protocol_version`

## Compatibility Matrix

| module_version | protocol_version | status |
| --- | --- | --- |
| 1 | 0.1 | supported, deprecated |
| 1 | 0.2 | supported, active |

## Deprecation Lifecycle

1. `active`: fully supported
2. `deprecated`: accepted at runtime, but replacement is returned by validators
3. `removed`: rejected by runtime

For current release:

- `0.1` is `deprecated`
- `0.2` is `active`

## Runtime Validation Rules

Runtime validation must reject:

1. unsupported `protocol`
2. unsupported `protocol_version`
3. unsupported `module_version`
4. incompatible `module_version` to `protocol_version`
5. no shared execution targets

Runtime validation must return:

1. compatibility result
2. deprecation phase
3. replacement version if deprecated
4. sunset milestone if deprecated

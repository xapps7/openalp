from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

from .decompile import to_python_like
from .bundle import BundleError, create_bundle, run_bundle
from .format import ALPFormatError, parse_module
from .handshake import HandshakeError, compatibility, parse_hello
from .integrity import (
    create_manifest,
    create_rsa_demo_signature_manifest,
    create_signature_manifest,
    verify_manifest,
    verify_rsa_demo_signature_manifest,
    verify_signature_manifest,
    write_demo_rsa_keypair,
    write_manifest,
    write_signature_manifest,
)
from .opcodes import opname
from .profile import ExecutionProfile, ProfileError, load_profile
from .protocol import ProtocolError, RuntimeProfile, validate_runtime_compatibility
from .rawbuild import RawBuildError, build_alpb_file
from .transport import (
    EnvelopeError,
    LocalTransport,
    build_envelope_from_file,
    make_bundle_executor,
    parse_envelope,
    validate_envelope,
)
from .vm import VMError, run_module


def _read(path: pathlib.Path) -> bytes:
    return path.read_bytes()


def _resolve_profile(args: argparse.Namespace) -> ExecutionProfile:
    """Pick the execution profile for this invocation.

    A host may select a profile; it may not execute without one. Whichever
    profile is used is echoed in the command output, so the step budget is
    always recorded alongside the result it produced (D2 / finding F4).
    """
    path = getattr(args, "profile", None)
    if path:
        return load_profile(pathlib.Path(path))
    budget = getattr(args, "step_budget", None)
    if budget is not None:
        return ExecutionProfile(step_budget=budget)
    return ExecutionProfile.default()


def _add_profile_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", default=None, help="execution profile JSON (see samples/profile.default.json)")
    parser.add_argument(
        "--step-budget",
        "--max-steps",
        dest="step_budget",
        type=int,
        default=None,
        help="step budget for an ad-hoc profile; --profile takes precedence",
    )


def cmd_validate(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.path)
    try:
        module = parse_module(_read(path))
    except (OSError, ALPFormatError) as exc:
        print(f"INVALID: {exc}")
        return 1

    print(json.dumps({"status": "valid", "version": module.version, "entry": module.entry, "instructions": len(module.instructions)}))
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.path)
    try:
        module = parse_module(_read(path))
    except (OSError, ALPFormatError) as exc:
        print(f"INVALID: {exc}")
        return 1

    print(f"module: version={module.version} entry={module.entry}")
    for i, inst in enumerate(module.instructions):
        print(f"{i:04d}: {opname(inst.opcode):<10} a={inst.a:3d} b={inst.b:3d} c={inst.c:3d}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.path)
    try:
        profile = _resolve_profile(args)
        module = parse_module(_read(path))
        result = run_module(module, profile, trace=args.trace)
    except (OSError, ALPFormatError, VMError, ProfileError) as exc:
        print(f"ERROR: {exc}")
        return 1

    payload = {
        "halted": result.halted,
        "steps": result.steps,
        "stack": result.stack,
        "top": result.top,
        "output": result.output,
        "profile": profile.to_dict(),
    }
    if args.trace:
        trace = result.trace or []
        if args.trace_limit is not None:
            trace = trace[: args.trace_limit]
        payload["trace"] = trace
    print(json.dumps(payload))
    return 0


def cmd_handshake_validate(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.path)
    try:
        payload = json.loads(path.read_text())
        hello = parse_hello(payload)
        result = compatibility(hello)
    except (OSError, json.JSONDecodeError, HandshakeError) as exc:
        print(f"INVALID: {exc}")
        return 1
    print(json.dumps(result))
    return 0 if result.get("compatible") else 1


def cmd_runtime_validate(args: argparse.Namespace) -> int:
    module_path = pathlib.Path(args.path)
    hello_path = pathlib.Path(args.hello)
    try:
        module = parse_module(_read(module_path))
        hello = parse_hello(json.loads(hello_path.read_text()))
        result = validate_runtime_compatibility(
            RuntimeProfile(
                protocol=hello.protocol,
                protocol_version=hello.version,
                module_version=module.version,
                features=hello.features,
                targets=hello.targets,
            )
        )
    except (OSError, ALPFormatError, json.JSONDecodeError, HandshakeError, ProtocolError) as exc:
        print(f"INVALID: {exc}")
        return 1
    print(json.dumps(result))
    return 0


def cmd_decompile(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.path)
    try:
        module = parse_module(_read(path))
    except (OSError, ALPFormatError) as exc:
        print(f"INVALID: {exc}")
        return 1
    print(to_python_like(module))
    return 0


def cmd_checksum_create(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.path)
    try:
        manifest = create_manifest(path)
        out = write_manifest(path, manifest)
    except OSError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps({"status": "created", "path": str(out), "checksum": manifest.checksum}))
    return 0


def cmd_checksum_verify(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.path)
    manifest = pathlib.Path(args.manifest) if args.manifest else path.with_suffix(path.suffix + ".sha256.json")
    try:
        ok, reason = verify_manifest(path, manifest)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps({"valid": ok, "reason": reason, "manifest": str(manifest)}))
    return 0 if ok else 1


def cmd_sign_create(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.path)
    key = pathlib.Path(args.key)
    try:
        manifest = create_signature_manifest(path, key)
        out = write_signature_manifest(path, manifest)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps({"status": "created", "path": str(out), "signature": manifest.signature}))
    return 0


def cmd_sign_verify(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.path)
    key = pathlib.Path(args.key)
    manifest = pathlib.Path(args.manifest) if args.manifest else path.with_suffix(path.suffix + ".sig.json")
    try:
        ok, reason = verify_signature_manifest(path, key, manifest)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps({"valid": ok, "reason": reason, "manifest": str(manifest)}))
    return 0 if ok else 1


def cmd_keygen_demo_rsa(args: argparse.Namespace) -> int:
    prefix = pathlib.Path(args.prefix)
    try:
        pub, priv = write_demo_rsa_keypair(prefix)
    except OSError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps({"status": "created", "public": str(pub), "private": str(priv)}))
    return 0


def cmd_sign_rsa_create(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.path)
    key = pathlib.Path(args.key)
    try:
        manifest = create_rsa_demo_signature_manifest(path, key)
        out = path.with_suffix(path.suffix + ".rsa.sig.json")
        out.write_text(json.dumps({"algorithm": manifest.algorithm, "file": manifest.file, "signature": manifest.signature}, indent=2) + "\n")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps({"status": "created", "path": str(out), "signature": manifest.signature}))
    return 0


def cmd_sign_rsa_verify(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.path)
    key = pathlib.Path(args.key)
    manifest = pathlib.Path(args.manifest) if args.manifest else path.with_suffix(path.suffix + ".rsa.sig.json")
    try:
        ok, reason = verify_rsa_demo_signature_manifest(path, key, manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps({"valid": ok, "reason": reason, "manifest": str(manifest)}))
    return 0 if ok else 1


def cmd_determinism_report(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.path)
    try:
        profile = _resolve_profile(args)
        module = parse_module(_read(path))
    except (OSError, ALPFormatError, ProfileError) as exc:
        print(f"ERROR: {exc}")
        return 1

    hashes: list[str] = []
    tops: list[int | None] = []
    steps: list[int] = []
    for _ in range(args.runs):
        try:
            result = run_module(module, profile, trace=False)
        except VMError as exc:
            print(f"ERROR: {exc}")
            return 1
        payload = json.dumps({"top": result.top, "stack": result.stack, "steps": result.steps}, sort_keys=True)
        hashes.append(hashlib.sha256(payload.encode("utf-8")).hexdigest())
        tops.append(result.top)
        steps.append(result.steps)

    consistent = len(set(hashes)) == 1
    print(json.dumps({"runs": args.runs, "consistent": consistent, "output_hash": hashes[0] if hashes else None, "top_values": tops, "steps": steps, "profile": profile.to_dict()}))
    return 0 if consistent else 1


def cmd_build_raw(args: argparse.Namespace) -> int:
    src = pathlib.Path(args.src)
    out = pathlib.Path(args.out)
    try:
        build_alpb_file(src, out)
    except (OSError, RawBuildError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps({"status": "built", "src": str(src), "out": str(out)}))
    return 0


def cmd_bundle_create(args: argparse.Namespace) -> int:
    try:
        create_bundle(
            module_path=pathlib.Path(args.module),
            hello_path=pathlib.Path(args.hello),
            checksum_path=pathlib.Path(args.checksum),
            signature_path=pathlib.Path(args.signature),
            signature_key_path=pathlib.Path(args.key),
            out_path=pathlib.Path(args.out),
            binary=args.binary,
        )
    except (OSError, json.JSONDecodeError, BundleError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps({"status": "created", "bundle": args.out}))
    return 0


def cmd_bundle_run(args: argparse.Namespace) -> int:
    try:
        profile = _resolve_profile(args)
        result = run_bundle(pathlib.Path(args.bundle), pathlib.Path(args.key), profile)
    except (OSError, json.JSONDecodeError, BundleError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(
        json.dumps(
            {
                "output": result.output,
                "top": result.top,
                "steps": result.steps,
                "verified_checksum": result.verified_checksum,
                "verified_signature": result.verified_signature,
                "compatible": result.compatible,
                "profile": profile.to_dict(),
            }
        )
    )
    return 0


def cmd_transport_envelope_create(args: argparse.Namespace) -> int:
    try:
        envelope = build_envelope_from_file(
            pathlib.Path(args.payload),
            stream_id=args.stream,
            sequence=args.sequence,
            kind=args.kind,
            idempotency_key=args.idempotency_key,
            max_attempts=args.max_attempts,
            deadline_ms=args.deadline_ms,
            correlation_id=args.correlation_id,
        )
        pathlib.Path(args.out).write_text(envelope.to_json())
    except (OSError, EnvelopeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps({"status": "created", "envelope": args.out, "envelope_id": envelope.envelope_id}))
    return 0


def cmd_transport_envelope_validate(args: argparse.Namespace) -> int:
    try:
        envelope = parse_envelope(json.loads(pathlib.Path(args.path).read_text()))
        result = validate_envelope(envelope)
    except (OSError, json.JSONDecodeError, EnvelopeError) as exc:
        print(f"INVALID: {exc}")
        return 1
    print(json.dumps(result))
    return 0


def cmd_transport_send(args: argparse.Namespace) -> int:
    try:
        envelope = parse_envelope(json.loads(pathlib.Path(args.envelope).read_text()))
        transport = LocalTransport(
            executor=make_bundle_executor(pathlib.Path(args.key), _resolve_profile(args))
        )
        receipt = transport.send(envelope)
    except (OSError, json.JSONDecodeError, EnvelopeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(receipt.to_dict()))
    return 0 if receipt.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alp", description="ALP MVP CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate an ALP module")
    p_validate.add_argument("path")
    p_validate.set_defaults(func=cmd_validate)

    p_run = sub.add_parser("run", help="run an ALP module")
    p_run.add_argument("path")
    _add_profile_args(p_run)
    p_run.add_argument("--trace", action="store_true")
    p_run.add_argument("--trace-limit", type=int, default=None)
    p_run.set_defaults(func=cmd_run)

    p_inspect = sub.add_parser("inspect", help="inspect an ALP module")
    p_inspect.add_argument("path")
    p_inspect.set_defaults(func=cmd_inspect)

    p_handshake = sub.add_parser("handshake", help="ALP-Hello compatibility tools")
    p_handshake_sub = p_handshake.add_subparsers(dest="hs_command", required=True)
    p_hs_validate = p_handshake_sub.add_parser("validate", help="validate hello JSON and check compatibility")
    p_hs_validate.add_argument("path")
    p_hs_validate.set_defaults(func=cmd_handshake_validate)

    p_runtime = sub.add_parser("runtime", help="runtime compatibility tools")
    p_runtime_sub = p_runtime.add_subparsers(dest="runtime_command", required=True)
    p_runtime_validate = p_runtime_sub.add_parser("validate", help="validate module and hello compatibility")
    p_runtime_validate.add_argument("path")
    p_runtime_validate.add_argument("--hello", required=True)
    p_runtime_validate.set_defaults(func=cmd_runtime_validate)

    p_decompile = sub.add_parser("decompile", help="decompile an ALP module to Python-like code")
    p_decompile.add_argument("path")
    p_decompile.set_defaults(func=cmd_decompile)

    p_checksum = sub.add_parser("checksum", help="checksum manifest tools")
    p_checksum_sub = p_checksum.add_subparsers(dest="checksum_command", required=True)
    p_checksum_create = p_checksum_sub.add_parser("create", help="create checksum manifest")
    p_checksum_create.add_argument("path")
    p_checksum_create.set_defaults(func=cmd_checksum_create)
    p_checksum_verify = p_checksum_sub.add_parser("verify", help="verify checksum manifest")
    p_checksum_verify.add_argument("path")
    p_checksum_verify.add_argument("--manifest", default=None)
    p_checksum_verify.set_defaults(func=cmd_checksum_verify)

    p_sign = sub.add_parser("sign", help="signature manifest tools")
    p_sign_sub = p_sign.add_subparsers(dest="sign_command", required=True)
    p_sign_create = p_sign_sub.add_parser("create", help="create HMAC signature manifest")
    p_sign_create.add_argument("path")
    p_sign_create.add_argument("--key", required=True)
    p_sign_create.set_defaults(func=cmd_sign_create)
    p_sign_verify = p_sign_sub.add_parser("verify", help="verify HMAC signature manifest")
    p_sign_verify.add_argument("path")
    p_sign_verify.add_argument("--key", required=True)
    p_sign_verify.add_argument("--manifest", default=None)
    p_sign_verify.set_defaults(func=cmd_sign_verify)

    p_keygen = sub.add_parser("keygen-demo-rsa", help="write a deterministic demo RSA keypair")
    p_keygen.add_argument("prefix")
    p_keygen.set_defaults(func=cmd_keygen_demo_rsa)

    p_sign_rsa = sub.add_parser("sign-rsa", help="demo RSA signature tools")
    p_sign_rsa_sub = p_sign_rsa.add_subparsers(dest="sign_rsa_command", required=True)
    p_sign_rsa_create = p_sign_rsa_sub.add_parser("create", help="create demo RSA signature manifest")
    p_sign_rsa_create.add_argument("path")
    p_sign_rsa_create.add_argument("--key", required=True)
    p_sign_rsa_create.set_defaults(func=cmd_sign_rsa_create)
    p_sign_rsa_verify = p_sign_rsa_sub.add_parser("verify", help="verify demo RSA signature manifest")
    p_sign_rsa_verify.add_argument("path")
    p_sign_rsa_verify.add_argument("--key", required=True)
    p_sign_rsa_verify.add_argument("--manifest", default=None)
    p_sign_rsa_verify.set_defaults(func=cmd_sign_rsa_verify)

    p_det = sub.add_parser("determinism", help="determinism checks")
    p_det_sub = p_det.add_subparsers(dest="det_command", required=True)
    p_det_report = p_det_sub.add_parser("report", help="run module repeatedly and compare outputs")
    p_det_report.add_argument("path")
    p_det_report.add_argument("--runs", type=int, default=5)
    _add_profile_args(p_det_report)
    p_det_report.set_defaults(func=cmd_determinism_report)

    p_build_raw = sub.add_parser("build-raw", help="build .alp from numeric .alpb source")
    p_build_raw.add_argument("src")
    p_build_raw.add_argument("out")
    p_build_raw.set_defaults(func=cmd_build_raw)

    p_bundle = sub.add_parser("bundle", help="agent bundle tools")
    p_bundle_sub = p_bundle.add_subparsers(dest="bundle_command", required=True)

    p_bundle_create = p_bundle_sub.add_parser("create", help="create an ALP bundle from module+sidecars")
    p_bundle_create.add_argument("--module", required=True)
    p_bundle_create.add_argument("--hello", required=True)
    p_bundle_create.add_argument("--checksum", required=True)
    p_bundle_create.add_argument("--signature", required=True)
    p_bundle_create.add_argument("--key", required=True)
    p_bundle_create.add_argument("--out", required=True)
    p_bundle_create.add_argument("--binary", action="store_true", help="write compact binary bundle (.alppb)")
    p_bundle_create.set_defaults(func=cmd_bundle_create)

    p_bundle_run = p_bundle_sub.add_parser("run", help="verify and run an ALP bundle")
    p_bundle_run.add_argument("--bundle", required=True)
    p_bundle_run.add_argument("--key", required=True)
    _add_profile_args(p_bundle_run)
    p_bundle_run.set_defaults(func=cmd_bundle_run)

    p_transport = sub.add_parser("transport", help="transport envelope and delivery tools")
    p_transport_sub = p_transport.add_subparsers(dest="transport_command", required=True)

    p_envelope = p_transport_sub.add_parser("envelope", help="execution envelope tools")
    p_envelope_sub = p_envelope.add_subparsers(dest="envelope_command", required=True)

    p_envelope_create = p_envelope_sub.add_parser("create", help="build an execution envelope around a payload")
    p_envelope_create.add_argument("--payload", required=True, help="bundle or module file to wrap")
    p_envelope_create.add_argument("--stream", required=True, help="ordering domain")
    p_envelope_create.add_argument("--sequence", type=int, required=True)
    p_envelope_create.add_argument("--kind", choices=["bundle", "module"], default=None)
    p_envelope_create.add_argument("--idempotency-key", default=None)
    p_envelope_create.add_argument("--max-attempts", type=int, default=1)
    p_envelope_create.add_argument("--deadline-ms", type=int, default=None)
    p_envelope_create.add_argument("--correlation-id", default=None)
    p_envelope_create.add_argument("--out", required=True)
    p_envelope_create.set_defaults(func=cmd_transport_envelope_create)

    p_envelope_validate = p_envelope_sub.add_parser("validate", help="validate an execution envelope")
    p_envelope_validate.add_argument("path")
    p_envelope_validate.set_defaults(func=cmd_transport_envelope_validate)

    p_transport_send = p_transport_sub.add_parser("send", help="deliver an envelope through the local reference transport")
    p_transport_send.add_argument("--envelope", required=True)
    p_transport_send.add_argument("--key", required=True)
    _add_profile_args(p_transport_send)
    p_transport_send.set_defaults(func=cmd_transport_send)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

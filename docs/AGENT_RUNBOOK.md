# OpenALP Agent Runbook

The standing instruction set for an autonomous session working this repo — whether fired on a schedule, resumed by a human, or handed to a fresh model. It replaces per-session handoff docs: the state lives in [`docs/status.json`](/Users/cedcoss/Documents/AgentLang/alp_mvp/docs/status.json), and this file says how to act on it.

## Orientation, every run

Repo: `/Users/cedcoss/Documents/AgentLang/alp_mvp`

1. `git log --oneline -5 && git status --porcelain`
2. Read `docs/status.json`. It is the authoritative work queue. Prose roadmap docs do **not** override it.
3. Read the tail of `docs/WORKLOG.md` for what previous runs did.
4. Establish the baseline gate **before** changing anything:

```bash
export PYTHONPATH="$PWD"
python3 -m unittest discover -s tests -p 'test_*.py' -q
./scripts/launch_check.sh
```

If the baseline is already red, do not start new work. Diagnosing and fixing that breakage is the whole run.

## Standing rules

1. **Never push to git.** Local commits only. Publication to `github.com/xapps7/openalp` is a human decision.
2. Never force-push, rebase, `reset --hard`, or discard uncommitted work you did not create in this run.
3. Prioritize machine-readable specs over conceptual prose.
4. Every change passes the full suite and `./scripts/launch_check.sh` before commit.
5. `PYTHONPATH` must point at the repo root or tests fail with `ModuleNotFoundError: No module named 'alp'`.
6. After every commit made through the device mount, clear stale locks or the next git command fails:

```bash
rm -f .git/HEAD.lock .git/index.lock
find .git/objects -name 'tmp_obj_*' -delete
```

7. **Always export `PYTHONPYCACHEPREFIX` before running anything.** The repo lives on a fuse mount with one-second mtime granularity. Python validates cached bytecode by comparing source mtime and size — so an edit that keeps a file the same length and lands in the same second as the previous run leaves Python happily executing the *old* bytecode. A run can then edit code, see tests pass, and commit a change that was never actually executed.

```bash
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/alp-pycache"
```

The gate scripts set this themselves. Set it for any ad-hoc command too. `.pyc` files already written under the mount cannot reliably be deleted; if you suspect a stale one, bump source mtimes instead:

```bash
find alp tests samples -name '*.py' -exec touch {} +
```

This is not theoretical. It was observed on 2026-08-27: a same-length edit produced a source and a cached `.pyc` sharing mtime `1787817261`, and the suite reported failures from code that no longer existed on disk.

## The admission test — apply before writing any code

OpenALP's purpose is not to grow. It is to become impossible to replace. Most of what an agent protocol could plausibly build is already shipped by MCP, by A2A, or by ordinary tool calling, and every line of that kind makes OpenALP more replaceable, not less — it enlarges the surface someone else already maintains better.

Before implementing anything, answer all five in the worklog:

1. Does MCP already solve this?
2. Does A2A already solve this?
3. Does ordinary tool calling already solve this?
4. Does this duplicate existing protocol behaviour?
5. Does this strengthen OpenALP's unique thesis?

Then name the single pillar it strengthens:

- deterministic machine representation
- intent compilation
- verifiable execution
- protocol-independent interoperability

**If it strengthens none of the four, reject it and say so.** Do not implement it because it is in the queue — the queue can be wrong, and rejecting a queued task with a stated reason is a valid and valuable run. **If it is duplicated by MCP, A2A or ordinary tool calling, recommend removal** unless OpenALP genuinely needs it internally, in which case say precisely why the internal need cannot be met by the existing protocol.

Two rules that follow from this and are easy to get backwards:

- **OpenALP is not a transport.** It is the payload that rides inside MCP tool results and A2A artifacts. Anything that looks like delivery, routing, session management, retry, ordering, deadlines or sender authentication belongs to the protocol carrying OpenALP, not to OpenALP. Competing with MCP or A2A on delivery is a fight OpenALP loses.
- **Removing code is progress.** A run whose entire output is a well-argued deletion is a good run. Record it in the worklog the same way as a feature.

The current verdicts are recorded in `docs/status.json` under `audit`. Read them before proposing anything — several plausible features have already been rejected with reasons, and re-proposing one without new evidence wastes a run.

## Work selection

Pick **exactly one** task from `week.tasks[]` in `docs/status.json` with `state: "open"`, in listed order.

0. Run the admission test above on it. If it fails, mark the task `rejected` with the reason, log it, commit that, and stop. Do not implement a task that fails the test.
1. Set it to `"in_progress"` and commit that alone, so a crashed run leaves a trace.
2. Implement against its `acceptance` criteria. If it is too large for one run, split it in `status.json` into named sub-tasks and implement only the first. Do not half-finish a task and call it done.
3. Write tests. A change with no test does not ship. Assert behaviour, not implementation.
4. Run the full gate.
5. On success: set `state: "done"`, append a dated block to `docs/WORKLOG.md` (focus, output, hours), make one local commit whose message explains *why*, not just what.

## Failure handling

If the gate fails and you cannot fix it within the run:

1. `git checkout -- .` to restore the last good commit
2. set the task back to `"open"` with a `blocked_reason` field
3. log what you tried in `docs/WORKLOG.md`
4. commit only the status and worklog, and stop

A clean repo and an honest report beat a broken tree.

## Empty queue

Do not invent work. Report that the queue is empty, name the two or three highest-value candidates you would add and why, and stop without committing code.

## Judgement

Prefer the change that removes a structural gap over the one that adds a feature. If you find something genuinely wrong — a spec contradicting the implementation, a test asserting the wrong thing, a security claim the code does not support — say so plainly and fix it in preference to the queued task, noting the swap in the worklog. Do not soften findings. Do not report work as complete that is not.

## Report

Close with a short plain-language summary under 200 words: which task, what changed, test count before and after, gate status, commit hash, and anything a human needs to decide.

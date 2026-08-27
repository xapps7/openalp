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

## Work selection

Pick **exactly one** task from `week.tasks[]` in `docs/status.json` with `state: "open"`, in listed order.

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

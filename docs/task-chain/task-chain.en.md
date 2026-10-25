# Task Chains — the engineering foundation of a long-running LLM-native project

> This article comes from the project behind this repository: how we organize long-horizon LLM work across **task chains**. It is a selectively published, reader-friendly projection of internal engineering documents — rewritten, not mirrored. Within this repository's maintenance loop, the chain system's role can roughly be viewed as an iteration gate conjoining mechanical and semantic verdicts; this repository exhibits only fixed-version snapshots of it, and the maintenance of this repository's content is likewise carried out by the exhibited version.

## 1. The problem: sessions end, work must not

An LLM session has a **single-session quality boundary**: a context window, an attention budget, a token allowance. Any unit of work larger than that boundary degrades if forced through one session — so long-running work must be decomposed across sessions.

But decomposition without structure rots. Later sessions build on unverified earlier output; intent drifts one handoff at a time; after a few weeks nobody can answer *which step changed this file, and why*. Task chains exist to make decomposition itself an engineering artifact:

- **every step is inspected before anything is built on it**;
- **every change is attributable** to a chain and a task;
- **every handoff states concretely verifiable expectations** for the successor.

A chain is not a workflow engine and not a task queue for humans. It is a directory of plain files that an LLM can read, write, and be held to — the cheapest possible substrate that still carries the three guarantees above.

## 2. The task model

```
LLM_{n-1}  --handoff-->  LLM_n  --handoff-->  LLM_{n+1}
              <--inspect--        <--inspect--
```

Any LLM in a chain performs three operations. All three, none optional:

### 2.1 INSPECT — gate on the predecessor

Trust is not inherited along a chain. An uncaught error at step *n* becomes, unchanged, the foundation of step *n+1* — and at a session boundary nobody is there to catch it for you: the previous LLM is gone, and only the files it left behind can be talked to. INSPECT replaces "trust the predecessor" with "verify the predecessor": against the expectations its handoff stated (expected outcomes + declared open risks) and the tool-preprocessed list of changes, check output against claims and for net harm to the project, and produce a verdict (PASS / FAIL / WARN) with specific deviations. It must precede EXECUTE — building on unverified ground just transfers the cost of checking to some future session where the error is far harder to locate. On FAIL, the response scales with the deviation: repair (small), revert (large), or mark as a known risk and continue — with the decision itself on record.

An example. The previous task delivered an input-deduplication module; its handoff claimed "lines arriving within the silence window belong to the same interaction intent". The successor does not build on it. It replays three input classes — slow line-by-line typing, one pasted block, and two arrivals separated by an interval sitting exactly on the window edge — and the third exposes a defect that merges two independent inputs into one. Deviation recorded, small repair, continue. The gate paid for itself right there: leaked upward, the same defect would have surfaced as "the upstream occasionally drops events", an order of magnitude costlier to localize.

The reverse case is just as real: if the successor's task is fixing three typos in a document, the predecessor's foundation has almost nothing to do with it, and a full INSPECT is pure overhead. Gate density should match the load the foundation actually bears — this model serves work where the next step really is built on the previous one, not all work.

### 2.2 EXECUTE — do the subtask, leave a trace

Half of EXECUTE's claim is "get the work done"; the other half is "make it attributable". Every change must be capturable by tooling — invisible edits do not exist — and the execution record must declare its chain and task explicitly; otherwise, three months later, "which step changed this, and why" can only be answered by archaeology. Traceability is not audit decoration: across sessions, memory is the first thing to fail, and structure is the only witness that survives.

For example, take a subtask implementing dependency-declaration validation, whose spec requires "the dependency fields form a DAG — a topological order exists, no cycles". The execution order is: write the failing test first (construct a cyclic declaration set, assert the validator rejects it), then implement, then run the full regression; the record notes the chain, the task, the changed files, and the test evidence. When someone later asks why the topology check rejects a self-dependency, the answer lives in structure, not in anyone's memory.

The boundary is equally plain: an exploratory spike — answer unknown, output likely discarded, nothing to be built on top of it — does not merit attribution bookkeeping. Do it, conclude, and record the conclusion itself as the deliverable; pretending it is a foundation stone is less honest than saying it is not one.

### 2.3 HANDOFF — write the successor's inspection contract

HANDOFF is closing out your own work from the successor's point of view: what was completed, what in the changes deserves checking, where things are known-incomplete. Its core discipline: *expectations must be concretely verifiable*. "The protocol parses correctly" fails; "boundary values 0/127/128/16383/2097151/268435455/2147483647 encode and decode bit-identically to the reference" passes. The difference is not wording but decidability: the former leaves the successor an unactionable belief; the latter leaves a checklist that can simply be executed. Open risks are the same — declare them explicitly; silence is not "no risk", it is risk transferred to someone who does not know about it.

A contrast says it best. A bad handoff: "optimized performance, should be fine" — the successor's INSPECT has nowhere to start, degenerates into a full re-audit, and the chain into a diary. A good handoff: "writes switched from per-record flush to batched commit; expect: bulk-write latency down by roughly an order of magnitude, tail latency of single writes up; check: no half-written state after crash recovery (test X covers it); known risk: degeneration in tiny-batch regimes, uncalibrated" — the successor finishes a real inspection in half an hour.

And when a task is the chain's final piece, HANDOFF faces not a successor but the chain's own closure and archival: state the acceptance comparison and the unfinished remainder, so that "closed" is a verifiable declaration, not a disappearance.

## 3. Five premises — when decomposition is valid at all

Chains are not free; they pay for themselves only when all five premises hold. Violating any one means the chain model does not apply — fall back to single-task mode.

1. **Single-session quality boundary.** The task *cannot* be completed with acceptable quality in one session. Decomposition is therefore not "possible" but *mandatory*; forcing one session collapses quality. Detect: subtask complexity exceeds ~80% of a session's context, or expected token spend exceeds a session budget.
2. **Decomposable with known side effects.** The task splits into interdependent subtasks, and the split itself introduces no new unknowns: split points have explicit reasons, and information loss at boundaries is recorded rather than discovered later.
3. **Equivalence of completion.** The AND of all subtask pass criteria equals the parent's pass criteria — nothing missing, nothing extra. If all subtasks pass but the parent goal is not met, the decomposition had a gap, and the gap must be traceable to a specific criterion.
4. **Dependencies and parallelism expressible as a chain.** The dependency fields form a DAG — a topological order exists, no cycles. Dependency means sequential chain (INSPECT the predecessor's work); independence means parallel chains (INSPECT only at merge points).
5. **Inter-task influences known and explicit.** When two subtasks touch the same file or the same function, the conflict possibility is declared, parallel execution is forbidden, and they are serialized.

## 4. Execution principles

**Decomposition, horizontal and vertical.** Horizontal: same level, parallel, independent — disjoint anchor sets, merge points verified by cross-INSPECT. Vertical: dependency chains, each step built on the previous, each step INSPECTed. Mixed: split independent dimensions first, then chain each dimension internally. When a decomposition has broad scope and hard-to-assess side effects, the only reliable verdict is an integration test — side effects invisible to review are exactly what end-to-end execution exposes.

**INSPECT is a responsibility, with a boundary.** Checking the predecessor is not optional courtesy — it is what makes the successor's own work meaningful. But INSPECT is a gate, not the main task: if the predecessor's output is so poor that INSPECT would become the work (open risks beyond acceptance, more than half the pass criteria failing, or interface-only stubs), the inspection *escalates* into an EXECUTE that repairs or completes the predecessor's output — explicitly marked as such.

**Tools take the mechanical, the LLM takes the semantic.** Mechanical screening — what changed, which files, which declarations — belongs to the tool; the LLM consumes the preprocessed checklist and performs semantic judgment: logical correctness, interface consistency, alignment with design intent. One session corresponds to exactly one task file; all three operations are recorded in that file. Hand-grepping for a predecessor's artifacts is an anti-pattern: if the tool cannot surface it, the process is wrong.

**First tasks get a special INSPECT.** There is no predecessor to check, so the inspection turns on the decomposition itself: is the split too coarse for the quality boundary, is the first task chosen to be simple but quality-critical. The first task is the chain's foundation; inspecting it is inspecting the chain.

**Compact semantic fields, mechanical fields to the tool.** Human/LLM-facing narration lives in compact `{KEY:value}` entries (pattern-matchable, no prose tax); timestamps, statuses, declarations, and match counts are written by tooling. The LLM never hand-maintains bookkeeping it can get wrong.

**Iteration with ordered succession.** The chain format itself iterates. The discipline: one schema version is the authority; old chain files stay readable (reader-side compatibility profiles); format migration is an explicit, golden-tested transform — never a silent rewrite; deprecation is not deletion; and the chain system builds each new format version on the chain system itself (the carrying chain dogfoods what it carries).

## 5. Object model — the design decisions

The chain system's object model is a set of deliberate trade-offs, each recorded as a decision with its rationale:

| Aspect | Decision | Rationale |
|---|---|---|
| Storage | Plain files on disk: one directory per chain | LLM-readable without any tooling, git-diffable, trivially greppable; no database earns its keep here |
| Artifact trinity | Per chain: a *manifest* (identity + lifecycle declarations), a *charter* for standing chains (direction of travel, hash-anchored), and *task files* | Manifest is the chain's single fact source; the charter keeps long-lived duties from drifting; task files are append-only history |
| One file, one session | A task file corresponds to one LLM session; INSPECT/EXECUTE/HANDOFF all recorded in-file | Attribution and continuity: the file *is* the session's contract with the chain |
| Chain kinds | `terminal` (built, then archived) vs `standing` (perpetual duty; dormant ≠ invalid) | Some work finishes; some work is a standing responsibility that sleeps between cycles |
| Status as declaration | `planned / executing / delivered / closed / retired` are declared values, not inferences | State transitions are semantic judgments; they are *registered* with evidence, and detectors flag inconsistencies afterwards |
| Two-layer verdicts | Tools enforce *format facts* only (schema validity, enum bounds); quality states pass through *soft gates* backed by recorded evidence facets | Mechanical checks close over what they can prove; everything else is declared with traces, refusable, or explicitly overridden with a recorded reason |
| Epochs | Reopening a chain with a cause starts a new epoch; counters are machine-maintained | Long-lived chains accumulate rounds; epochs keep history intelligible |
| Archive in place | Archiving is a declaration in the manifest — zero file moves; deep-freeze to a history area is optional | Discovery filters by declaration; moving files breaks links and history |
| Traceability | Change = supersede pointer + retirement pointer; delete = retirement (files are never deleted); close-time content-hash snapshots detect post-close modification | History is evidence; tampering (even accidental) must be detectable, not prevented by trust |
| Reading marks | ASCII marks: task `+` closed / `o` open; chain `[dormant]` / `[archived]` | A whole chain's state readable in one screen of monospace |
| Tooling | One tool owns all mechanical operations (declarations, views, sweeps, lookups); the LLM never hand-greps for artifacts | Mechanical truth has a single writer; the LLM's role stays semantic |

## 6. Command surface

The chain tool's current face, fifteen commands (an earlier workflow family — `init`, `inspect`, `intent`, `handoff`, `test-init`, `split`, `merge`, and bookkeeping commands — is retired in place: kept readable, no longer on the active face):

| Command | Face |
|---|---|
| `new` | Create a chain: manifest registration (identity, momentum, kind) |
| `task` | Add a task file inside a chain (time-phased continuation, not a split) |
| `start` / `close` / `retire` | Declare lifecycle transitions (soft-gated on recorded facets; hash snapshots at close) |
| `charter` | View / declare a charter revision for a standing chain (hash-anchored) |
| `archive` / `unarchive` | In-place visibility flip; cause required |
| `reopen` | Open a new epoch; cause required; archived chains auto-unarchive |
| `status` | Lifecycle views with ASCII marks, status filtering |
| `sweep` | Consistency sweep — suggests, never executes |
| `lookup` | Search across manifests and charters, including archived and frozen |
| `freeze` | Optional deep-freeze into the history area |
| `checklist` | Read-only INSPECT preprocessing: prior handoffs, soft-gate rehearsal, scaffold |
| `migrate` | Explicit legacy-format transform (kept for the record; the frozen family is deliberately not migrated) |

## 7. Version discipline

The chain format has iterated more than once, and the iteration itself follows rules rather than mood:

- **Old artifacts stay readable.** Every reader handles the formats it may encounter; nothing needs converting before it can be opened.
- **Deprecation is not deletion.** Retired commands and frozen chains remain on disk, documented, findable by explicit path.
- **Migration, when it happens, is explicit.** One-way, golden-tested transforms with their provenance recorded — silent rewrites are structurally absent.
- **This repository exhibits fixed snapshots.** What you read here is one version of the chain system; the maintenance of this repository's own content is likewise carried out by the exhibited version.

## 8. A live specimen

[`chain_schema.py`](chain_schema.py) beside this article is the schema module of the exhibited version, published under the project's direct-copy rules (ruling-anchor comments stripped, inline internal identifiers cleaned, behavior docstrings kept). It is the neutral module both sides of the system read — the runtime that derives chain views, and the toolchain that validates writes — and it is small enough to read in one sitting: the declaration state machine, the snapshot hashing that makes tampering detectable, the format-fact validator, and the compatibility profile for older files.

For the compact document format used across this project's internal records — of which this repository's [GENE.md](../../GENE.md) is a live specimen — see the root [README](../../README.md).

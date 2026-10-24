# commensal — engineering notes from an LLM-native project

> commensal is a long-running, LLM-native software project. This repository is not its mirror — it is its public projection: practices, mechanism designs, and lessons selectively published from the project's private working records, rewritten to be reader-friendly.

This README also exists in [中文](README.zh-CN.md) and in [gene-compact](GENE.md) format — a compact, LLM-optimized document format (see [Planned content](#planned-content)).

## Why this repository exists

The project itself evolves in a private repository. Along the way it has accumulated a set of unconventional engineering practices: how to organize long-horizon LLM work across twenty-plus task chains spanning weeks; how to keep specification documents growing sub-linearly as decisions accumulate; how to govern LLM output with fail-closed mechanical gates that live outside the model. The value of these practices does not depend on whether the project's research goals hold — but until now they existed only in internal documents written in a compact format optimized for LLMs rather than humans.

This repository exists to rewrite that independently valuable engineering experience as public, reader-friendly text.

We do not publish the main repository directly, for two reasons. First, the research core of the project is not yet finalized; premature full publication would compromise later validation, which includes blind tests requiring uncontaminated external participants. Second, the internal documents use a compact format that would be hostile to read as-is — publishing means rewriting, and rewriting means selecting.

## Intended operation (target state)

- **A projection, not a mirror.** Everything here is generated from the private source repository via whitelist selection plus reader-friendly re-rendering. This repository is disposable and rebuildable from source; its commit history carries no promise.
- **A semi-automatic publishing pipeline.** Mechanically collect the diff since the last release → an LLM renders it (de-internalized, rewritten to be reader-friendly) → mechanical checks scan for secrets and internal identifiers, fail-closed — what fails never leaves → human final review → push.
- **Cadence anchored to semantic completion points.** Releases follow the closure of internal units of work, not a calendar.
- **No internal git history is mirrored.** Each release is a content snapshot.

## Actual operation (current state)

*As of 2026-10-24 17:00 (UTC+8)*

- Releases are currently **rendered and pushed by hand**; the pipeline above does not exist yet — building it will itself be among the first things published here.
- **Low maintenance commitment.** This repository is read-only by intent. Issues are welcome, but timely responses are not promised.
- Releases are irregular, driven by internal evolution.

## Planned content

- **The task-chain system** — task chains as the engineering foundation of a long-running, LLM-native software project; within this repository's maintenance loop, their role can roughly be viewed as an iteration gate conjoining mechanical and semantic verdicts. This repository exhibits only fixed-version snapshots of the chain system; maintenance of the repository's content will likewise be carried out by the exhibited version.
- **Document information processing** — applying the memory / organizing / forgetting mechanisms currently in use by the project, reflexively, to its own specification documents: a three-face architecture (source template → partition printing → projection) that keeps document growth sub-linear.
- **gene-compact** — a compact document format designed for LLM readers. [GENE.md](GENE.md) in this repository is a live specimen.
- **Fail-closed gates** — mechanical gates governing LLM output: underdetermination, symmetry law, provenance resolution.
- **Field notes** — engineering lessons rewritten (and redacted) from the project's friction records.
- *(later)* an introduction to the research core, once validation has progressed far enough.

## License

All rights reserved. Quoting and discussion with attribution are welcome.

## Name

*commensal* is Latin — *com mensa*, "at the same table". The Chinese name 同桌 (tóngzhuō, "deskmate") is a character-by-character calque: com = 同 (same), mensa = 桌 (table).

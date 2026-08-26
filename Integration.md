---
description: >
  Use Knowledge before planning or implementing a change in an unfamiliar GitHub
  repository. Knowledge supplies evidence-backed engineering context; it does
  not choose or generate the implementation.
---

# Knowledge — LLM Integration Contract

This document is for an LLM, coding agent, or tool orchestrator that uses
**Knowledge** while helping a contributor work on a GitHub issue or pull
request.

## Mission and boundary

Knowledge is a **pre-implementation engineering-context layer**. Its job is to
reduce avoidable guesswork before code is planned or changed. It investigates
the issue, repository evidence, linked discussion, and connected implementation
so that a contributor can make an informed decision.

Knowledge is **not** an implementation planner, code generator, autonomous
committer, or substitute for a maintainer's product decision. The integrating
agent remains responsible for deciding whether the evidence supports a proposal
and for obtaining any required approval.

Use Knowledge before you:

- propose an implementation approach for an unfamiliar issue;
- edit a subsystem whose behavior or ownership is unclear;
- infer intent from an issue title, filename, or README alone; or
- treat a prior issue, PR, or agent summary as current fact.

Do not use Knowledge as ceremony for mechanical, already-understood changes.
For example, a maintainer-provided one-line typo correction in a known document
does not need a repository investigation.

## Required operating model

Treat the repository's source, issue/PR discussion, and documented rules as
evidence with different purposes:

| Evidence | What it can establish |
| --- | --- |
| Source code and tests | Current implemented behavior and interactions |
| Issue/PR text and comments | Requested outcome, decisions, constraints, and historical context |
| Repository documentation | Stated intent, setup, and contribution policy |
| File and directory names | Leads to investigate; never proof of behavior |
| Earlier Knowledge output or agent memory | A lead that must be verified against current evidence |

Do not turn a filename match into an architectural claim. Do not equate a
README statement with current behavior when source evidence disagrees. Do not
fill an evidence gap with a conventional implementation pattern.

## When and how to query Knowledge

### 1. Gather a precise request

Supply as much of the following as is available:

- repository owner and name;
- issue or pull-request number and URL;
- issue title, body, and relevant comments if the integration cannot retrieve
  them itself;
- the contributor's goal or question (for example, *"What must I understand
  before fixing this?"*);
- any known files, failing tests, branch/commit, or constraints; and
- whether the agent needs issue understanding, PR understanding, architecture,
  onboarding, contribution guidance, feature flow, or historical context.

The issue URL or description is the minimum useful input. If it is ambiguous,
include the ambiguity in the question; do not silently replace it with an
assumed requirement.

### 2. Ask a pre-implementation question

When Knowledge is installed as the GitHub bot, post one focused request on the
issue or PR:

```text
@Knowledge What does this issue require, which existing implementation path is
most relevant, which repository constraints apply, and what remains unknown
before I propose a change?
```

`/knowledge` is an equivalent trigger. The local CLI integration can make the
same request after the repository's token and provider configuration are set:

```bash
python knowledge_engine.py \
  --owner <owner> \
  --repo <repository> \
  --issue <number> \
  --comment "@Knowledge <focused question>" \
  --author <contributor>
```

Use follow-up questions when the first answer exposes a material gap. Prefer a
specific question over asking for a generic repository overview. For example,
ask where a value enters a flow and where it is consumed, or why a linked PR
changed a particular file.

### 3. Read and validate the response

Knowledge normally returns a natural-language engineering handoff with evidence
files and repository permalinks. Extract the working brief below from that
answer, but do **not** force Knowledge itself into a rigid response template.

Before relying on a claim:

1. Follow the cited file or discussion when the claim materially affects the
   implementation.
2. Confirm that the cited implementation is on the relevant current revision.
3. Separate an explicit fact from an implementation inference and from an
   unknown.
4. Treat a missing citation or inaccessible file as an evidence gap, not as
   confirmation.

If Knowledge cannot run, cannot access the repository, or returns insufficient
evidence, report that limitation. A coding agent may perform the equivalent
bounded, evidence-first investigation itself, but must label that it is doing
so and must not claim that Knowledge verified the result.

## Required pre-implementation brief

Before proposing code changes, the integrating agent must produce a concise
brief containing these fields. Use `Unknown` rather than guessing.

| Field | Required content |
| --- | --- |
| Issue interpretation | The requested outcome, scope, and explicit non-goals, grounded in the issue and discussion |
| Evidence summary | What the inspected source, tests, docs, and linked issues/PRs establish |
| Relevant implementation path | A short, ordered set of files/components to read, with why each belongs in the path and how they connect |
| Constraints | Maintainer directives, contribution rules, compatibility/security expectations, and documentation-versus-code discrepancies |
| Existing examples | Similar implementation, PR, test, or convention to study; say `None found` only after a bounded search |
| Unknowns and assumptions | Facts not established, assumptions requiring validation, and their impact |
| Maintainer decisions needed | Specific questions that block a safe proposal, with the decision each answer would unlock |
| Confidence and citations | Confidence appropriate to the evidence, plus links/paths for material claims |

The brief is a decision aid, not a design approval. Do not begin implementation
when a material unknown changes the intended behavior, public API, security
model, compatibility promise, or ownership boundary.

## Constraints that the integrating agent must preserve

1. **Evidence first.** Inspect relevant source before asserting behavior. Trace
   actual call, data, or dependency relationships; do not merely list keyword
   matches.
2. **Bounded investigation.** Expand from the issue to connected code, tests,
   references, and linked PRs as needed. Do not indiscriminately read the whole
   repository.
3. **Truthful uncertainty.** Clearly mark evidence, inference, and unknowns.
   Never convert a plausible guess into a requirement.
4. **Issue discussion matters.** Treat maintainer directions in issue/PR
   comments as constraints when they are explicit. If comments conflict, flag
   the conflict rather than selecting a winner.
5. **Current code wins for behavior.** Documentation expresses intent; source
   and tests establish current behavior. Flag any conflict for the contributor
   or maintainer.
6. **No silent boundary crossing.** Do not propose or implement a change to a
   protected or risk-sensitive area without explicitly flagging it and obtaining
   the appropriate maintainer confirmation.
7. **No invented protection list.** A repository may not declare formal
   protected modules. In that case, do not claim one exists. Treat the areas
   below as risk-sensitive defaults, and ask maintainers to confirm ownership
   and the required review path.
8. **Keep control with people.** Do not present the context brief as a
   maintainer decision, approval, or authorization to merge.

### Risk-sensitive defaults for this repository

Knowledge-Agent does not currently publish a formal protected-module manifest.
Until maintainers define one, flag these areas before proposing a behavior
change:

- GitHub authentication, credentials, token handling, and webhook verification
  (`github_auth.py`, `webhook_server.py`, and configuration);
- untrusted input and command execution boundaries;
- LLM provider behavior and network-facing adapters (`providers.py`);
- persistent context/memory behavior and compatibility shims
  (`memory_store.py`, `pr_context.py`);
- the evidence and prompt contract (`KNOWLEDGE.md`, `knowledge_engine.py`); and
- GitHub Action or deployment behavior (`.github/workflows/`).

This is a risk flag, not a ban. The agent should state the affected boundary,
the expected impact, and the specific approval or policy clarification needed.

## Mandatory maintainer-deferral rules

Stop and ask a maintainer a focused question instead of guessing when any of the
following is true:

- the issue has two or more plausible interpretations with materially different
  behavior or scope;
- the desired product behavior, acceptance criteria, or non-goals are missing;
- maintainer comments, documentation, tests, or current code conflict;
- a public API, stored data format, permission model, security control, or
  backwards-compatibility behavior may change;
- the change reaches a risk-sensitive area and repository policy or ownership is
  not explicit;
- no evidence-backed existing pattern exists and the choice would create a new
  architectural convention; or
- the evidence needed to validate a material claim is inaccessible or absent.

A good deferral is answerable and decision-oriented:

```text
The issue asks for X, but the repository evidence supports both A and B. A
changes the public command behavior; B preserves it but limits the feature.
Which behavior is intended, and should the existing command remain compatible?
```

Do not defer for routine implementation details that are already decided by
clear code, tests, repository rules, or explicit issue instructions.

## Example prompts

### First pass on an issue

```text
@Knowledge I am preparing to work on this issue. Explain the requested outcome,
the relevant implementation flow, the files I should inspect in order and why,
any maintainer constraints, comparable code or tests, and what cannot be
verified from repository evidence.
```

### Clarifying an ambiguous issue

```text
@Knowledge Identify the issue statements or discussion comments that leave the
acceptance criteria ambiguous. For each ambiguity, show the relevant evidence,
the implementation paths it changes, and a concise maintainer question.
```

### Studying a prior implementation

```text
@Knowledge This issue references PR #<number>. Trace the relationship from the
issue through that PR's changed files into the current implementation. Which
parts are still relevant, which have changed, and what constraints should a new
fix preserve?
```

### Checking a proposed approach before coding

```text
@Knowledge I am considering changing <file/component> to achieve <outcome>.
Based on the current implementation, what calls into it, what it calls, which
tests or existing patterns constrain the change, and which assumptions require
maintainer confirmation?
```

## Completion gate for a coding agent

An agent may move from context gathering to an implementation proposal only
when it can explain the requested outcome, name an evidence-backed path through
the relevant code, identify applicable constraints, and either resolve material
unknowns or obtain maintainer direction. Its proposal must cite the evidence it
relies on and explicitly call out any risk-sensitive boundary.

If this gate is not met, return the context brief and the smallest set of
maintainer questions needed to meet it. Do not manufacture a solution.

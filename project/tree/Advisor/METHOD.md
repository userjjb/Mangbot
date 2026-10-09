# How the Advisor runs a study (first version, 2026-09-27)

The Advisor plans, the Clerks gather, and the Advisor combines what they find into a memo for the
Architect. This is the first version. Improve it after each study (see "Retrospective" below).

```
topic ─▶ PLAN ─▶ briefs ─▶ Clerks (parallel, Sonnet) ─▶ dispatches ─▶ SYNTHESIS ─┬─▶ memo (../memos/)
            ▲                                                                   │
            └──────── replan: new questions, gaps, contradictions ◀─────────────┘
```

## Roles

- **Advisor** (this main chat, in `Advisor/`):
  - chooses and scopes the topic with the user, and writes the plan;
  - splits the work into assignments and writes the briefs;
  - reads every dispatch critically, checks the claims that matter, and resolves contradictions;
  - decides whether another pass is needed, and writes the memo;
  - asks the user when something is a judgement call.
- **Clerk** (the subagent `clerk`, `.claude/agents/clerk.md`, model Sonnet): takes one bounded
  assignment, reads its sources fully, and writes one **dispatch** with evidence tags
  (**[SEEN]** / **[REPORTED]** / **[INFERRED]**). A Clerk can't see the big picture, can't ask
  questions, and can't launch other agents.

## Where things live

Each study gets a folder `Advisor/studies/<YYYY-MM-DD>-<slug>/`:

| File | Content |
|---|---|
| `plan.md` | Goal, questions, sources, the assignment list (id, question, sources, status), pass log, decisions |
| `briefs/<id>.md` | The exact brief given to each Clerk (so runs are reproducible) |
| `dispatches/<id>.md` | What each Clerk wrote |
| `synthesis.md` | The Advisor's working notes: cross-dispatch table, contradictions and how they were resolved, what was verified |
| `scratch/` | Clerk scratch files, if any |

Fetched or generated data that outlives one study (corpora, extracted tables) goes in
`Advisor/data/<name>/` with a README, not in the study folder.

The finished memo goes to `../memos/<date>-<slug>.md`. The study folder stays as its audit trail.
Update `plan.md` as you go, so a study can continue in a later session.

## 1. Plan

- **Goal:** what the Architect will do with the answer. Write it in one line, and keep it in view.
- **Questions:** 3–8 concrete ones.
- **Sources**, and their reliability: code and data files are primary; forum posts and docs are
  secondary; our logs are observation.
- **Split into assignments.** Each one should:
  - fit one Clerk: roughly under 100k words of source, or one clearly bounded chunk of code or
    data;
  - be answerable on its own;
  - not overlap other assignments, unless the overlap is deliberate for cross-checking.
- Useful ways to split: by source (one file or chunk each), by question, or a deliberate
  **cross-check pair** (two Clerks answer the same question from different sources, such as forum
  vs code).
- Start with a first pass of about 3–6 Clerks. It's better to replan than to over-plan.
- **Numbers by script, judgement by Clerk** (lesson of the danger-table study): compute anything
  arithmetic (damage, speed, counts) with a script in `Advisor/data/` and hand it to the Clerks as
  input columns. Clerk arithmetic was the main source of errors. Check numbers with the same script,
  never by hand.
- For table studies, give each Clerk a CSV slice as input and ask for a CSV in `scratch/` as well as
  the dispatch; a shared rules file (scale, assumptions, verified facts) keeps parallel Clerks
  consistent. Give each Clerk only the "already known" claims for its own slice.

## 2. Brief (template)

The prompt to a Clerk *is* its brief. Save a copy in `briefs/<id>.md`.

```
Study: <slug> — assignment <id> (pass <n>)
Context (for orientation only): <2–4 lines: what the study is for; our character: throwaway
  Half-Orc Warrior, solo, stair-scumming, mostly 0–1500 ft; server MAngband 1.5.x>
Question(s): <numbered, concrete>
Sources: <exact paths / URLs / line or entry ranges>
Scope: <include / skip>
Already known (check against it, report contradictions): <bullets or a pointer to a memo section>
Output: write the dispatch to /projectnb/jbrcs/mangband/Advisor/studies/<study>/dispatches/<id>.md,
  ≤ <N> words, in the dispatch format of your instructions. <any extra table required>
Scratch (if needed): /projectnb/jbrcs/mangband/Advisor/studies/<study>/scratch/
```

Launch Clerks in parallel, in a single message, with `run_in_background`.

## 3. Read the dispatches

For each dispatch:
- Did it answer the question? Is its coverage complete?
- Spot-check the **[SEEN]** claims that matter: open the cited `path:line`. At least the ones the
  memo will rely on, and every surprising one. Treat **[REPORTED]** and **[INFERRED]** as leads,
  not facts.
- Collect its contradictions and leads.

Record the result in `synthesis.md`: verified, corrected, or unresolved.

## 4. Replan (another pass?)

Launch another pass when:
- dispatches contradict each other;
- a lead looks important;
- coverage has holes;
- the answer to one question changes another.

Log each pass in `plan.md`. Stop when the goal's questions are answered well enough for the
Architect to act; if not, when further passes would only add detail.

## 5. Memo

Write the memo the same way as before (see `../memos/2026-09-26-forum-distillation.md`):
- a short "how this was made" (sources, passes, what was verified);
- the most important findings first, each with its evidence;
- recommendations split into Pilot rules, Navigator doctrine and HANDBOOK text;
- the contradictions with current docs, in a table;
- coverage and gaps;
- **What I lacked** (since 2026-10-08, the Architect's complaints channel): missing data, logs that didn't record
  what the study needed, slow or wrong tools, access, time — separate from findings; "None" is fine. Collect the
  Clerks' "What I lacked" sections into it. The Architect copies it into `runs/complaints.md`.

Mark code-verified claims **[code ✓]**. Addressing it to the Architect.

After the memo:
- update memory pointers (the SYNC rule);
- add the study to the backlog file's history;
- write a short **Retrospective** at the end of `plan.md`: what worked with the Clerks and what to
  change in this method or in `clerk.md`.

## 6. Lessons from the studies so far (2026-09-27 → 10-03; details in each plan.md retrospective)

- **Numbers by script, judgement by Clerk.** Compute damage, prices, counts and replays with a script
  in `data/`; give Clerks the numbers as inputs. Check numbers with the same script, never by hand.
- **Do the cheap script first.** A data-file diff or an extraction script often gives the key fact
  before the Clerks finish (e.g. `monster.txt` unchanged since 2008; 1352 message calls extracted).
- **Split by the structure of the source:** by file group for code, by release (tag ranges) for
  history, by layer for a pipeline (server → client → bot → agent), plus one Clerk on *what our own
  runs actually did* — that Clerk is usually the most practical.
- **Give Clerks question + starting files and let them follow the code**; they will step outside the
  list to answer, and should flag it.
- **For log studies, hand Clerks the clock alignment** (events.jsonl restarts at t=0 per Pilot process;
  match acks to decisions acts).
- **Verify the claims the memo leans on** by opening the cited lines; Clerk errors were misreadings
  (inverted index, wrong headline threshold, mislabelled log field), all caught this way. Also check
  the *consumer side* of protocol claims (one false alarm about repeat packets died on a client read).
- **Shared rules file** (scale, assumptions, verified facts, vocabulary) for parallel Clerks; give each
  only the "already known" claims for its slice; deliberate small overlaps act as cross-checks.
- **Memos for the Architect:** lead with what to change, quick wins as a numbered list, `[code ✓]`
  marks, a contradictions table, coverage/gaps. Send a short note to `to_architect/` with each memo.

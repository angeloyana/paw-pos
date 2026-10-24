# Documentation guide

Setup, commands, and user workflows are in the [project README](../README.md).
Contributor workflow and commit rules are in [AGENTS.md](../AGENTS.md).

## Start of each session

1. Read this guide.
2. Read the [feature index](features/INDEX.md) for current work and status.
3. Read the spec for the task in `docs/features/`.
4. Read only the living docs listed in the spec's **Touches** field.

If no task spec exists, ask the user to provide one or offer to draft one before
writing code. Follow `AGENTS.md` when requirements are unclear or code and docs
disagree.

## Living docs

| Document | Contents |
| --- | --- |
| [FEATURES.md](FEATURES.md) | Current capabilities and acceptance criteria |
| [BUSINESS_PROCESS.md](BUSINESS_PROCESS.md) | Roles, shop workflows, and business rules |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layers, service interfaces, data flow, and transactions |
| [DATABASE.md](DATABASE.md) | Tables, columns, constraints, and seed data |
| [UI_UX.md](UI_UX.md) | Screens, dialogs, shortcuts, and interaction rules |
| [TECH_STACK.md](TECH_STACK.md) | Libraries, setup conventions, and coding standards |

Living docs describe the current system. Update the affected docs together with
the behavior they describe; use the documentation rules in `AGENTS.md` to choose
which ones to list under **Touches**. List additional documentation paths when a
task changes a guide, setup instructions, or the changelog.

## Feature tracking

Create a numbered spec from [the template](features/TEMPLATE.md) and register it
in the [index](features/INDEX.md). Use `planned`, `in progress`, or `done`; keep
the index and spec status consistent. Record unfinished work in the spec and
check acceptance items only after verifying them.

The [initial implementation plan](IMPLEMENTATION_PLAN.md) is a frozen historical
record of the completed build, including its recorded verification results.
Future features belong in individual specs. Its phase instructions apply to
that initial build. Use `AGENTS.md` for the current workflow.

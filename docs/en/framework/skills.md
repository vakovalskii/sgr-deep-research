# Skills

Skills are reusable, on-demand instruction packages (the Anthropic *Agent
Skills* model). Each skill is a directory with a `SKILL.md` file — YAML
frontmatter plus a markdown body. SGR Agent Core auto-registers skill
`name` + `description` into the agent system prompt so the agent can invoke a
skill autonomously, and also surfaces skills as **commands** over ACP, the CLI,
and the HTTP server.

## What a skill looks like

```
skills/
  citation-style/
    SKILL.md
  concise-answer/
    SKILL.md
```

`SKILL.md`:

```markdown
---
name: citation-style
description: Formats research citations in a consistent numbered style. Use when writing reports that reference web sources.
---

# Citation style

1. Number every source in order: [1], [2], ...
2. Collect all sources under a `## Sources` heading.
```

### Frontmatter

| field           | required | notes                                                              |
|-----------------|----------|--------------------------------------------------------------------|
| `name`          | yes      | ≤ 64 chars; lowercase letters, digits, hyphens; no `anthropic`/`claude` |
| `description`   | yes      | non-empty, ≤ 1024 chars; write in third person, say *what* and *when* |
| `license`       | no       | SPDX id or text                                                    |
| `allowed-tools` | no       | advisory list of tool names the skill uses                        |
| `metadata`      | no       | free-form mapping (version, author, ...)                          |
| `disable-model-invocation` | no | `true` hides the skill from the model catalog (user command only) |
| `user-invocable` | no      | `false` hides the skill from command menus (model-only)           |

If `name` is omitted it defaults to the directory name.

## Progressive disclosure

1. **Level 1 — metadata**: `name` + `description` are always injected into the
   system prompt (a compact catalog block), so the model knows the skill exists.
2. **Level 2 — body**: the `SKILL.md` body is loaded only when the skill is
   invoked (the `use_skill` tool returns it into the conversation).
3. **Level 3 — resources**: any bundled files are read only when needed.

## Enabling skills

Skills work out of the box: **by default** the agent scans

1. `./.agent/skills` (project, relative to the current working directory)
2. `~/.agent/skills` (personal)

If those folders are missing or empty, nothing breaks — the agent runs normally
with no skills. To customize, add a `skills` block to an agent (or globally, at
the top level) in `config.yaml`:

```yaml
agents:
  sgr_agent:
    base_class: SGRToolCallingAgent
    tools:
      - reasoningtool
    skills:
      enabled: true            # default true; set false to disable skills
      paths:                   # override the default roots (relative to CWD)
        - ./my-skills
      include: null            # optional allowlist of skill names to activate
      exclude: null            # optional denylist of skill names
```

`skills.paths`, when set, **replaces** the default roots. Later roots override
earlier ones by name. The per-entry description budget in the prompt listing is
a global setting: `execution.max_skill_desc_chars` (default 500).

When any skill is available, the agent's toolkit automatically gains the
`use_skill` tool.

## Invoking a skill

There are two ways a skill is invoked:

1. **Autonomously (the model decides).** The system prompt gains an
   `AVAILABLE_SKILLS` block listing each model-invocable skill and instructing
   the agent to call `use_skill` when a task matches. Calling
   `use_skill <name>` returns that skill's body into the conversation
   (progressive disclosure level 2).
2. **Explicitly (the user references it).** If a user message mentions a skill
   by name with a leading slash — `/citation-style` — that skill's body is
   injected into the prompt. This works in **every mode** (ACP, CLI, and the
   OpenAI-compatible server), because the reference is expanded centrally in
   `AgentFactory.create`. The reference may appear anywhere in the message
   (`please use /concise-answer`); slashes inside URLs/paths are ignored.

## Discovering skills as commands

- **ACP** (`sgracp`): user-invocable skills are advertised to the client as
  `available_commands`, so they appear in the client's slash-command menu.
- **CLI**: `sgrsh --list-skills -c config.yaml` prints the available skills.
- **HTTP server**: `GET /v1/skills` (optional `?model=<agent>`) lists skills per
  agent.

## Security & trust

Skills are **trusted content**, on the same level as `config.yaml` and custom
tool code: a skill body is injected verbatim into the model context when
invoked. The default roots `./.agent/skills` and `~/.agent/skills` are scanned
automatically, so opening a repository that ships a `.agent/skills/` directory
will auto-load its authors' instructions. Only run skills from sources you
trust, and review third-party `SKILL.md` files before use. The loader caps each
`SKILL.md` at 1 MiB and skips unreadable files.

## Authoring tips

- Write the `description` in third person; include both *what it does* and *when
  to use it* — this is what the model matches against.
- Keep `SKILL.md` focused (under ~500 lines); move long material into separate
  reference files.
- Use gerund or noun-phrase names (`processing-pdfs`, `citation-style`); avoid
  vague names like `helper` or `utils`.

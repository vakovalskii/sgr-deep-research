# Skills

Skills are reusable, on-demand instruction packages (the Anthropic *Agent
Skills* model). Each skill is a directory with a `SKILL.md` file — YAML
frontmatter plus a markdown body. SGR Agent Core auto-registers skill
`name` + `description` into the agent system prompt so the agent can invoke a
skill autonomously, and also surfaces skills as **commands** over ACP and MCP.

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

Add a `skills` block to an agent (or globally) in `config.yaml`:

```yaml
agents:
  sgr_agent:
    base_class: SGRToolCallingAgent
    tools:
      - reasoningtool
    skills:
      enabled: true            # default true
      paths:                   # extra skill roots (relative to config.yaml)
        - ./skills
      include: null            # optional allowlist of skill names
      exclude: null            # optional denylist of skill names
      max_desc_chars: 500      # per-entry description budget in the prompt
```

Skill roots are scanned in this order (later overrides earlier by name):

1. `~/.sgr/skills` (personal)
2. `<config dir>/skills` (project)
3. every path in `skills.paths`

When any skill is available, the agent's toolkit automatically gains the
`use_skill` tool.

## Autonomous invocation

The system prompt gains an `AVAILABLE_SKILLS` block listing each model-invocable
skill and instructing the agent to call `use_skill` when a task matches. The
agent decides on its own; calling `use_skill` with a skill name returns that
skill's body into the conversation.

## Skills as commands

- **ACP** (`sgracp`): user-invocable skills are advertised to the client as
  `available_commands` (slash commands). Typing `/citation-style ...` expands the
  skill body into the turn.
- **MCP**: `python -m sgr_agent_core.skills.mcp_server --config config.yaml`
  serves skills as MCP **prompts** (`prompts/list` / `prompts/get`), which MCP
  clients render as slash commands.
- **CLI**: `sgrsh --list-skills -c config.yaml` prints the available skills.
- **HTTP server**: `GET /v1/skills` (optional `?model=<agent>`) lists skills per
  agent.

## Security & trust

Skills are **trusted content**, on the same level as `config.yaml` and custom
tool code: a skill body is injected verbatim into the model context when
invoked. Once an agent enables `skills`, the roots `~/.sgr/skills` and
`<config dir>/skills` are always scanned, so opening a repository that ships a
`skills/` directory will auto-load its authors' instructions. Only enable skills
from sources you trust, and review third-party `SKILL.md` files before use. The
loader caps each `SKILL.md` at 1 MiB and skips unreadable files.

## Authoring tips

- Write the `description` in third person; include both *what it does* and *when
  to use it* — this is what the model matches against.
- Keep `SKILL.md` focused (under ~500 lines); move long material into separate
  reference files.
- Use gerund or noun-phrase names (`processing-pdfs`, `citation-style`); avoid
  vague names like `helper` or `utils`.

# Skills subsystem — design & specification

Status: draft (feat/skills)
Author: feat/skills work
Layered per `.cursor/rules/architecture.mdc` (bottom-up, one class at a time, TDD).

## 1. Motivation

Add first-class **Agent Skills** to SGR Agent Core, modeled on the Anthropic
"Agent Skills" pattern (a `SKILL.md` file with YAML frontmatter + markdown body,
progressive disclosure). Two capabilities are required:

1. **Autonomous invocation** — the agent automatically *registers* available
   skills into its system prompt (name + description only, "progressive
   disclosure" level 1) so the LLM can decide, on its own, to invoke a skill.
   Invoking a skill loads its full body (level 2) into the conversation.
2. **Skills as commands** — skills are surfaced as user-visible **commands**
   through the protocol layers: ACP `available_commands` (slash commands in ACP
   clients such as Zed) and an optional MCP prompts server. This mirrors how
   codex / Claude Code / Cursor expose reusable prompts/skills as commands.

## 2. What a skill is (Anthropic model)

A skill is a directory containing a `SKILL.md`:

```
skills/
  pdf-processing/
    SKILL.md            # required: frontmatter + body
    scripts/            # optional bundled resources (level 3)
    references/
```

`SKILL.md` frontmatter (YAML). The portable open standard requires exactly two
fields — `name` and `description`; the rest are optional extensions.

| field           | required | validation / notes                                                 |
|-----------------|----------|--------------------------------------------------------------------|
| `name`          | yes      | ≤ 64 chars; only lowercase letters, digits, hyphens; no XML tags; not "anthropic"/"claude" |
| `description`   | yes      | non-empty; ≤ 1024 chars; no XML tags; third person; *what it does* + *when to use* |
| `license`       | no       | SPDX id or text                                                    |
| `allowed-tools` | no       | advisory allowlist of tool names the skill uses (soft, documented) |
| `metadata`      | no       | free-form dict (version, author, ...)                              |

Validation is enforced at parse time (Anthropic spec rules). Body: markdown
instructions (level-2 content, keep under ~500 lines / ~5k tokens); push long
material into reference files loaded on demand.

### Progressive disclosure (three levels)

- **Level 1 — metadata**: `name` + `description` always injected into the system
  prompt so the model knows the skill exists and when to reach for it.
- **Level 2 — body**: the `SKILL.md` markdown body, loaded into context only when
  the skill is invoked.
- **Level 3 — bundled files**: scripts/resources under the skill dir, referenced
  from the body and read/run only as needed.

## 3. Discovery

Skill roots are scanned (in order; later roots override same-named skills):

1. Packaged/builtin skills dir (optional, shipped with an example).
2. User dir: `~/.sgr/skills` (personal).
3. Project dir: `./.sgr/skills` relative to `config_dir`.
4. Explicit dirs from config (`skills.paths`) and per-agent `skills:` selection.

A skill dir is any immediate subdirectory that contains a `SKILL.md`.

## 4. Architecture (layered)

### Layer 1 — data model + loader (no deps)

- `sgr_agent_core/skills/models.py`
  - `SkillMetadata(BaseModel)`: `name`, `description`, `license: str | None`,
    `allowed_tools: list[str]`, `metadata: dict`.
  - `Skill(BaseModel)`: `metadata: SkillMetadata`, `body: str`, `path: Path`.
    Convenience props: `name`, `description`.
- `sgr_agent_core/skills/loader.py`
  - `SkillLoader.load_skill(dir: Path) -> Skill` — parse `SKILL.md`
    (frontmatter via a tiny YAML front-matter splitter; no new dependency —
    PyYAML already present). Validate required fields; raise `SkillError`
    on malformed/missing.
  - `SkillLoader.discover(root: Path) -> list[Skill]` — scan subdirs.

### Layer 2 — registry + config

- `sgr_agent_core/skills/registry.py`
  - `SkillRegistry` — runtime catalog (dict name -> Skill). Unlike ToolRegistry
    it is populated by scanning dirs (skills are data, not subclasses).
    Methods: `register`, `get`, `list_items`, `load_from_paths(paths)`,
    `clear`.
- Config: `SkillsConfig(BaseModel)` added to `AgentConfig`
  (`skills: SkillsConfig | None`), with:
  - `paths: list[str]` — extra skill roots.
  - `enabled: bool = True`.
  - `include: list[str] | None` / `exclude: list[str] | None` — filter by name.
  Per-agent selection via `AgentDefinition.skills: list[str]` (names) — resolved
  in a validator mirroring `agent_level_tools_validator`.

### Layer 3 — prompt injection + invocation tool

- `PromptLoader.get_system_prompt(..., available_skills=...)` — render a
  `{available_skills}` block (numbered `name: description`). Default
  `system_prompt.txt` gains an `<AVAILABLE_SKILLS>` section. Always pass the
  kwarg (empty string when no skills) so custom templates using the placeholder
  never KeyError, and templates without it are unaffected (`str.format` ignores
  extra kwargs).
- `sgr_agent_core/tools/skill_tool.py`
  - `SkillTool(SystemBaseTool)` — `tool_name = "use_skill"`. Field:
    `skill_name: str`. `__call__` looks up the skill (from
    `context.available_skills` / SkillRegistry), returns the level-2 body as a
    string (which the agent appends to conversation). Unknown skill -> helpful
    error string listing available skills. This is the autonomous-invocation
    vehicle and flows through both function-calling and SGR union paths via the
    registry — same pattern as `SearchToolsTool`.

### Layer 4 — agent + factory wiring

- `AgentContext` gains `available_skills: list[Skill]` (default empty) so tools
  can resolve skills without global state.
- `BaseAgent._prepare_context()` passes
  `available_skills=self.available_skills` to `PromptLoader.get_system_prompt`.
  `BaseAgent.__init__` accepts `skills: list[Skill] | None`.
- `AgentFactory.create` resolves skills (from `SkillRegistry` +
  `agent_def.skills` + config paths), injects `SkillTool` into the toolkit when
  skills are present, and threads the skill list into the agent + context.

### Layer 5 — protocol command surfaces

- **ACP**: `SGRACPBridge` sends an `AvailableCommandsUpdate` session update
  after `new_session` (and on agent switch), advertising each skill as an
  `AvailableCommand(name, description, input=UnstructuredCommandInput(...))`.
  A prompt of the form `/skill-name args...` is mapped to invoking that skill
  (prepend the skill body / run `use_skill`).
- **MCP (optional/stretch)**: a `SkillsMCPServer` (FastMCP) exposing each skill
  as an MCP **prompt** (`@mcp.prompt`) — the MCP primitive clients render as
  slash commands (`prompts/list`, `prompts/get`). Symmetric inverse of
  `MCP2ToolConverter`.
- **CLI**: `sgrsh --list-skills` prints discovered skills; `/skill` handling in
  chat loop (nice-to-have).
- **Server**: `GET /v1/skills` lists discovered skills (OpenAI-adjacent).

## 5. Testing plan (TDD, red first)

- `tests/test_skill_loader.py` — frontmatter parsing, required-field validation,
  discovery, malformed handling.
- `tests/test_skill_registry.py` — register/get/list, path loading, override.
- `tests/test_skills_config.py` — config parse, per-agent selection validator.
- `tests/test_prompts.py` (extend) — `{available_skills}` rendering.
- `tests/test_skill_tool.py` — `use_skill` returns body / errors.
- `tests/test_agent_factory.py` (extend) — factory injects SkillTool + skills.
- `tests/test_acp_bridge.py` (extend) — available_commands advertised; `/name`
  routes to skill.
- `tests/test_skills_e2e.py` (`@pytest.mark.e2e`) — end-to-end autonomous
  invocation with a mocked LLM choosing `use_skill`.
- Mode checks: ACP, CLI, OpenAI server.

## 5a. Listing budget & invocation semantics

- **Listing budget (level 1).** Injecting many skills must not blow the system
  prompt. Each rendered entry is `name: description` with the description
  truncated to a per-entry cap (`SkillsConfig.max_desc_chars`, default 500).
  This mirrors Claude Code's skill-listing budget (~1% context, ~1536-char
  per-entry cap). The name is always shown in full.
- **Invocation = prompt injection.** When `use_skill` runs, the level-2 body is
  returned as the tool result and appended to the conversation, where it
  persists for the rest of the run (matching Anthropic semantics). No isolated
  subagent in v1.
- **ACP push mechanism.** The bridge advertises commands via
  `client.session_update(session_id, AvailableCommandsUpdate(available_commands=[
  AvailableCommand(name, description, input=UnstructuredCommandInput(hint=...))]))`
  — same `session_update` channel the streaming generator already uses.

## 6. Non-goals / constraints

- No new runtime dependency (reuse PyYAML, fastmcp, acp already present).
- Backward compatible: agents without skills behave exactly as before
  (`{available_skills}` optional, SkillTool only added when skills exist).
- English comments; 120-char lines; ruff clean.

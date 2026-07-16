# Checkpoints & Rollback

SGR agents can snapshot their execution state as they run, so you can **roll
back to an earlier step**, **restore an agent after a process restart**, and
**resume a session** (including over the Agent Client Protocol).

Checkpointing is **opt-in**: with it disabled (the default) agents behave
exactly as before and take no snapshots.

## What a checkpoint contains

Each checkpoint (`AgentCheckpoint`) captures everything needed to rebuild the
agent at a given step:

- `agent_id`, `def_name`, `step` (the iteration number) and `created_at`
- the original `task_messages` and the current `conversation`
- the restorable `context` — state, iteration, searches, sources, counters,
  `custom_context`, current reasoning and execution result

Runtime-only fields are intentionally excluded: the `asyncio` clarification
event (recreated on restore) and the resolved skills (re-resolved from config).

## Configuration

Enable checkpointing in the `execution.checkpoint` block:

```yaml
execution:
  checkpoint:
    enabled: true          # take a snapshot every step
    backend: "file"        # "memory" (per-process) or "file" (survives restarts)
    dir: "checkpoints"     # directory used by the file backend
    max_history: 20        # keep only the last N steps per agent (null = unbounded)
```

- **`memory`** keeps snapshots in process memory (lost on restart).
- **`file`** writes one JSON file per step under `dir/{agent_id}/`, so agents
  can be restored after a crash or restart.

A snapshot is taken at the **start of every iteration**, so the latest
checkpoint always holds the state up to and including the previous step — a
crash mid-step loses no committed progress.

## Programmatic API

Every `BaseAgent` exposes:

```python
agent.checkpoint()          # save a snapshot now, returns the AgentCheckpoint
agent.list_checkpoints()    # -> list[AgentCheckpoint] ordered by step
agent.rollback(step=2)      # restore conversation + context from step 2
agent.rollback()            # restore from the latest checkpoint
```

Rolling back replaces the live `conversation` and `context` with the saved
snapshot (a fresh clarification event is created). It raises `RuntimeError` if
no store is configured and `ValueError` if the step does not exist.

### Restoring a fresh agent

Rebuild an agent from a checkpoint via the factory:

```python
from sgr_agent_core import AgentFactory, FileCheckpointStore

store = FileCheckpointStore("checkpoints")
checkpoint = store.latest(agent_id)
agent = await AgentFactory.restore(checkpoint, checkpoint_store=store)
```

`restore` resolves the agent definition from `GlobalConfig` by `def_name`
(or takes an explicit `agent_def=`), keeps the checkpoint's id, and re-applies
the saved conversation and context.

## REST API

When checkpointing is enabled the HTTP server exposes:

- `GET /agents/{agent_id}/checkpoints` — list saved checkpoints.
- `POST /agents/{agent_id}/rollback` — body `{"step": 2}` (omit `step` for the
  latest); rolls a **live** agent back.
- `POST /agents/{agent_id}/restore` — rebuild an agent from its latest
  checkpoint (e.g. after a restart) and put it back in the server registry.

All three return `404` when checkpointing is disabled or no checkpoint exists.

## ACP session resume

The Agent Client Protocol bridge advertises `load_session=true`. Checkpoints
taken during a prompt are tagged with the ACP `session_id`, and `load_session`
rebuilds the session from its latest checkpoint — so a client can reconnect and
continue after a restart.

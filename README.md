# Delta Crew — PROPEL training setup

This Discord bot provides `/training setup` with a read-only preview and an
explicit **Are you sure?** confirmation before applying the PROPEL training
server blueprint.

## What it creates

- 53 functional, colour-coded roles plus 11 colour-coded divider roles.
- 9 private categories and 49 channels.
- Flight Deck, Cabin Crew, Ground Crew, and Customer Service section channels
  are Discord Forum channels (the Discord UI may call these Discussion
  channels).
- Department information/results channels are read-only for trainees and
  writable by that department's certified trainer/evaluator roles.
- Training leadership can view and manage every managed channel.
- Existing Department Management and HR roles can view every managed channel.
  They are detected by name, accepted as command options, or configured with
  `TRAINING_GLOBAL_ACCESS_ROLES`.

The department categories deny `@everyone` and grant access only to that
department's roles. A member of one department cannot see another department's
category unless they also hold a role for it, are training leadership, have an
explicitly configured all-access role, or are a server administrator.

## Command

Only members with **Manage Server** can use the command.

- `/training setup action:Preview` shows exact create/reuse counts and any
  blockers. It never modifies the server.
- `/training setup action:Apply changes` shows the same plan and an **Apply
  changes / Cancel** confirmation. No changes occur until confirmation.
- The optional `department_management_role` and `human_resources_role` options
  explicitly grant existing roles read access to every managed channel.

## Safety and repeat runs

`data/training_setup_state.json` is an ownership ledger keyed by guild ID.

- Re-running the same blueprint reconciles by ID/name and creates no duplicate
  managed setup.
- A matching pre-existing role, category, or correctly typed channel is
  adopted, not claimed. Adopted resources are never deleted by this command.
- When `BLUEPRINT_VERSION` changes, only IDs recorded as bot-created are
  replaced. Role assignments are migrated to same-named replacement roles.
- A bot-created category containing an untracked channel is preserved so the
  untracked channel is not disturbed.
- Unknown permission overwrites on reused channels are preserved. The command
  changes only the overwrites needed to enforce its visibility model.
- A pre-existing channel with a requested name but the wrong type blocks apply
  instead of being deleted or duplicated.

Persist the `data/` directory (or point `TRAINING_SETUP_STATE_FILE` at durable
storage). Losing the ledger does not cause duplicates—the command reuses names—
but it will no longer claim those resources as safe to replace.

## Run it

1. Create a Discord application/bot and enable **Server Members Intent** in the
   Developer Portal. This is used to preserve member role assignments during a
   blueprint replacement.
2. Give the bot **Manage Roles** and **Manage Channels**, and place its bot role
   above the roles it creates.
3. Enable **Community** on the Discord server. Discord requires this for Forum
   (Discussion) channels; apply is blocked until it is enabled.
4. Install and start the bot:

   ```bash
   python -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   export DISCORD_TOKEN='your-token'
   export DISCORD_GUILD_ID='your-test-server-id'  # recommended while testing
   python bot.py
   ```

### Render Web Service

Create a Render **Web Service** with `python bot.py` as the start command.
Render injects `PORT`; the bot listens on `0.0.0.0:$PORT` and serves JSON health
responses at `/` and `/healthz`. You may set `/healthz` as Render's health check
path. When `PORT` is not set, such as during local development, the health server
does not start.

Render may print a PyNaCl warning. It is harmless for this bot: the training
blueprint creates voice channels, but the bot does not join voice or process
audio.

Render Free Web Services sleep after 15 minutes without inbound HTTP traffic,
so use a paid/non-sleeping instance for a reliably always-online Discord bot.
Render's filesystem is also ephemeral; use durable storage for
`data/training_setup_state.json` (or set `TRAINING_SETUP_STATE_FILE` to a durable
path).

For Docker, build with `docker build -t delta-crew .` and mount a persistent
directory at `/app/data` when running the container.

Run the dependency-free blueprint checks with:

```bash
python -m unittest discover -s tests -v
```

## Permission summary

| Area | Audience | Chat behavior |
| --- | --- | --- |
| PROPEL Information | All functional PROPEL roles | Welcome/info/announcements/schedule read-only; support chattable |
| Department information/results | That department only | Read-only to trainees; trainer/evaluator can post |
| Requested department sections | That department only | Forum discussions; trainer/evaluator can moderate |
| TSA/ATC sections | That department only | Regular text channels, chattable |
| Staff | Certified trainers/evaluators | Staff chat and logs chattable; Trainer Office voice |
| Alumni | Graduate/Alumni | Alumni chat chattable; graduation board read-only |
| Every area | PROPEL leadership | View, post, moderate, and manage |
| Every area | Department Management/HR | View/read access |

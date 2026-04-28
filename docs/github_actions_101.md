# GitHub Actions 101

## What is it?

GitHub Actions is a way to run code automatically in response to events in your repository. Think of it as a robot assistant that watches your repo and does things when you tell it to.

The core concept is simple:

```
Something happens in your repo  →  GitHub runs a script
       (the trigger)                    (the workflow)
```

---

## Workflows

A workflow is a YAML file stored in `.github/workflows/`. GitHub discovers every file in that folder automatically just by it being there — you don't need to register or enable anything in a dashboard. This project has three:

| File | What it does |
|---|---|
| `validate.yml` | Runs all tests on every push |
| `post_new.yml` | Posts new predictions to Bluesky on push |
| `reminders.yml` | Scans for reminders every day at 09:00 UTC |

---

## The machine is always fresh

This is the most important thing to understand. **Every run starts from zero.** GitHub spins up a brand new Ubuntu machine, runs your steps, then throws it away. No files, no dependencies, no memory of the previous run.

That's why almost every workflow starts with:

```yaml
- uses: actions/checkout@v4
```
This clones your repo onto the machine. Without it, your code doesn't exist there.

---

## Anatomy of a workflow

```yaml
name: Validate predictions       # displayed in the Actions tab

on:                              # trigger(s)
  push:
    paths:
      - "predictions/**"

jobs:
  validate:                      # job name (you choose it)
    runs-on: ubuntu-latest       # what machine to use

    steps:
      - uses: actions/checkout@v4          # clone the repo
      - name: Set up Python
        uses: actions/setup-python@v5      # install Python
        with:
          python-version: "3.11"
      - name: Run tests
        run: python scripts/validate_test.py
```

Each `step` either runs a shell command (`run:`) or calls a pre-built action (`uses:`).

Pre-built actions are reusable scripts published by GitHub or the community. Instead of writing the shell commands yourself, you call the action and it handles everything. `actions/checkout@v4` is maintained by GitHub itself: it clones your repo onto the machine. `actions/setup-python@v5` installs Python. The `@v4` / `@v5` part is a version tag that pins the action to a specific release so your workflow doesn't break if the action's authors make changes later.

---

## Triggers

### Push with path filter

`validate.yml` and `post_new.yml` only fire when specific files change. There is no point running tests if you edited a markdown file:

```yaml
on:
  push:
    paths:
      - "predictions/**"
      - "categories.yaml"
      - "scripts/**"
```

`post_new.yml` goes further — it only fires on pushes to `main`, ignoring other branches:

```yaml
on:
  push:
    branches:
      - main
    paths:
      - "predictions/*.yaml"
```

### Cron schedule

`reminders.yml` uses a cron schedule to fire every day at 09:00 UTC:

```yaml
on:
  schedule:
    - cron: "0 9 * * *"
```

Cron syntax has five fields:

```
minute  hour  day-of-month  month  day-of-week
  0      9         *          *         *
```

`*` means "every". So `0 9 * * *` = at minute 0 of hour 9, every day.

### Manual trigger

`reminders.yml` also includes `workflow_dispatch`, which adds a "Run workflow" button in the Actions tab, useful for testing without waiting for 09:00:

```yaml
on:
  schedule:
    - cron: "0 9 * * *"
  workflow_dispatch:
```

---

## Secrets

Workflows need credentials (like `BLUESKY_APP_PASSWORD`) but you never put those in the code. GitHub lets you store them as **secrets** — encrypted values that are accessible to workflows but invisible to everyone, including you, after you save them.

Set them in: **Settings → Secrets and variables → Actions → New repository secret**

Reference them in a workflow like this:

```yaml
- name: Post prediction
  env:
    BLUESKY_HANDLE: ${{ secrets.BLUESKY_HANDLE }}
    BLUESKY_APP_PASSWORD: ${{ secrets.BLUESKY_APP_PASSWORD }}
  run: python scripts/post_new.py "$file"
```

The `${{ secrets.NAME }}` syntax is GitHub's expression language for injecting values at runtime.

---

## Writing back to the repo

`reminders.yml` needs to save state after each run (`state/reminded.yaml`). Since the machine is always fresh, the only way to persist anything is to commit it back to the repo:

```yaml
- name: Commit updated reminder state
  run: |
    git config user.name "github-actions[bot]"
    git config user.email "github-actions[bot]@users.noreply.github.com"
    git add state/reminded.yaml
    git diff --cached --quiet || git commit -m "chore: update reminder state [skip ci]"
    git push
```

Two things worth noting:

- `git diff --cached --quiet || git commit`: only commits if there are actual changes, avoiding empty commits on days when no reminders fire
- `[skip ci]` in the commit message: tells GitHub not to trigger `validate.yml` when the bot pushes, preventing an infinite loop

This bot commit is also why you occasionally get diverged branches: if the bot pushes at the same time you do, your local branch falls behind. Fix it with `git stash && git pull --rebase && git stash pop && git push`.

---

## Permissions

Because `reminders.yml` writes back to the repo, it needs explicit write permission:

```yaml
jobs:
  reminders:
    runs-on: ubuntu-latest
    permissions:
      contents: write
```

By default, workflows only have read access. The `GITHUB_TOKEN` is a special secret GitHub provides automatically: you don't set it, it's always there.

---

## The Actions tab

In your GitHub repo, click **Actions**. Every workflow run is listed there. Green check means it passed, red X means something failed. Click any run to see the logs step by step.

That's your first stop when something breaks.

---

## The local ↔ remote rule

Changes to workflow files or scripts only take effect on GitHub **after you push**. The remote repo is what Actions sees. Your local copy is invisible to it. If a test is failing in CI and you fix it locally, the fix does nothing until it's pushed.

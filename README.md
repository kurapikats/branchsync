# BranchSync

Synchronize filtered commits across Git branches with reviewable output and optional cherry-pick automation.

BranchSync helps teams move selected commits between long-lived branches without manually comparing logs, copying commit hashes, or guessing what has already been applied.

## Why use BranchSync

Many teams maintain branches such as:

- `develop` -> active work
- `staging` or `testing` -> validation
- `release/*` -> controlled deployments
- `main` -> production

In that model, some commits need to be promoted selectively instead of merging the entire source branch. BranchSync finds commits that exist in one branch but not another, filters them by commit message and timeframe, and can cherry-pick them in order.

## What it does

- Fetches the latest remote branch references
- Finds matching commits in a source branch
- Compares them with a target branch
- Lists missing commits in chronological order
- Optionally cherry-picks them onto the target branch
- Optionally pushes the updated target branch
- Restores your original branch and stashed work

## Typical scenarios

### 1. Promote feature-specific fixes

You use commit prefixes such as `payments:` or `discount:` and only want those commits copied from `develop` to `testing`.

```bash
branchsync --source develop --target testing --prefix "discount:"
```

### 2. Backport urgent fixes

You need to apply recent hotfix commits from `main` to a release branch.

```bash
branchsync --source main --target release/1.8 --prefix "hotfix:" --since "10 days ago"
```

### 3. Review before applying

You want a safe report first, without changing anything.

```bash
branchsync --source develop --target staging --prefix "catalog:"
```

### 4. Apply commits automatically

You want to cherry-pick the missing commits after reviewing the list.

```bash
branchsync --source develop --target testing --prefix "discount:" --cherry-pick
```

### 5. Resolve conflicts with a default strategy

You know the target branch should prefer incoming or current changes.

```bash
branchsync --source develop --target testing --prefix "discount:" --cherry-pick --conflict incoming
```

### 6. Fully automate promotion

You want to skip prompts and push immediately after a successful run.

```bash
branchsync --source develop --target testing --prefix "discount:" --cherry-pick --push --yes
```

## Installation

### From source

```bash
git clone <repo-url>
cd branchsync
pip install .
```

### For development

```bash
pip install -e .[dev]
```

## CLI usage

```bash
branchsync --help
```

Key options:

- `--source`, `-s`: source branch, default `develop`
- `--target`, `-t`: target branch, default `testing`
- `--since`, `-d`: Git time expression, default `3 weeks ago`
- `--prefix`, `-p`: commit message prefix filter
- `--cherry-pick`, `-c`: apply missing commits to the target branch
- `--push`, `-u`: push the target branch after cherry-picking
- `--yes`, `-y`: skip confirmation prompts
- `--conflict`, `-x`: choose `incoming` or `current` conflict strategy

## Example output

```text
Found 3 unmerged commit(s):
------------------------------------------------------------------------------------------
2026-07-02 | 2ac51ab90d7e | discount: fix voucher rounding
2026-07-03 | 1b3a77d2f104 | discount: clamp negative totals
2026-07-05 | c9e6151c6d9f | discount: support grouped promotions
------------------------------------------------------------------------------------------
```

## How it decides a commit is missing

BranchSync compares normalized commit subjects between the source and target branches. It is designed for teams that use stable commit prefixes and consistent subject lines across branch promotions.

## Limitations

- It matches commits by subject, not patch identity
- It works best when commit subjects are structured and consistent
- It expects to run inside a Git repository with accessible branch refs

## Exit behavior

- Safe by default: listing mode changes nothing
- Cherry-pick mode aborts on unresolved conflicts
- Original branch and stashed work are restored before exit

## Roadmap

- Support custom matching strategies
- Add patch-based comparison mode
- Add machine-readable output

## Contributing

See `CONTRIBUTING.md`.

## License

MIT. See `LICENSE`.


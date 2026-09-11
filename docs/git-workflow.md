# Git Workflow and Pull Request Guide

Kuping Negara uses a lightweight Git Flow model with two long-lived branches and
short-lived topic branches.

## Branch Roles

| Branch | Lifetime | Base | Purpose |
| --- | --- | --- | --- |
| `main` | Long-lived | — | Stable/release-ready state |
| `develop` | Long-lived | `main` after release synchronization | Integration branch for reviewed work |
| `feat/<kebab-case>` | Short-lived | `develop` | New capability |
| `fix/<kebab-case>` | Short-lived | `develop` | Non-production bug fix |
| `docs/<kebab-case>` | Short-lived | `develop` | Documentation-only change |
| `test/<kebab-case>` | Short-lived | `develop` | Test-only change |
| `chore/<kebab-case>` | Short-lived | `develop` | Tooling/configuration/maintenance |
| `hotfix/<kebab-case>` | Short-lived | `main` | Urgent production correction |

Topic branch names use a lower-case prefix and short kebab-case description,
for example `feat/schema-validation` or `docs/api-contract`.

## Understanding Ahead and Behind

GitHub compares two commit histories:

- **ahead** means the branch contains commit(s) not present in the comparison
  branch;
- **behind** means the comparison branch contains commit(s) not present in the
  selected branch;
- a branch can be both ahead and behind after independent commits are made on
  both sides.

All branches are **not** expected to stay ahead of `main`.

- A new topic branch is initially equal to `develop`.
- It becomes ahead while work is committed.
- It may also become behind if `develop` advances during the work.
- After merge, the topic branch is deleted instead of being advanced forever.
- `develop` can temporarily become behind when a release merge creates a
  main-only merge commit; synchronize `main` back into `develop` after release.

The `behind` label is not proof of lost work or an error. Artificially adding
empty commits or force-updating completed branches only to change the counter is
not professional branch management.

## Starting Work

```bash
git switch develop
git pull --ff-only origin develop
git switch -c feat/short-description
```

Choose the branch type based on the change's primary purpose. Do not mix an
unrelated feature, refactor, and documentation rewrite in one Pull Request.

## Keeping a Topic Branch Current

Before requesting review, incorporate the latest `develop` state:

```bash
git fetch origin
git rebase origin/develop
```

Rebase only commits that have not been collaboratively based on by others. If a
shared branch must not be rewritten, merge `origin/develop` instead. Never force
push `main` or `develop`.

## Conventional Commits

Format:

```text
<type>(optional-scope): <imperative summary>
```

| Type | Usage | Example |
| --- | --- | --- |
| `feat` | New user/system capability | `feat(ingestion): add weekly program collector` |
| `fix` | Correct defective behavior | `fix(validation): reject empty tweet identifiers` |
| `docs` | Documentation only | `docs: expand project proposal` |
| `test` | Tests only | `test(preprocessing): cover URL normalization` |
| `refactor` | Internal change without behavior change | `refactor(training): isolate split strategy` |
| `style` | Formatting/whitespace only | `style: normalize markdown line endings` |
| `chore` | Maintenance, dependencies, configuration | `chore: update dev container image` |
| `ci` | CI/CD workflow | `ci: validate package on pull request` |

Rules:

- use imperative, specific summaries;
- keep one coherent intent per commit;
- do not use meaningless messages such as `update`, `fix stuff`, or `final`;
- include issue references and migration/breaking-change notes in the body;
- never include secrets or personal data in commit messages.

## Creating a Pull Request

### GitHub Web UI

1. Push the topic branch:

   ```bash
   git push -u origin docs/professional-documentation
   ```

2. Open the repository on GitHub and select **Compare & pull request**.
3. Set **base** to `develop` and **compare** to the topic branch.
4. Use a Conventional Commit-style title.
5. Complete every relevant section of the Pull Request template.
6. Include the purpose, implementation scope, verification commands/results,
   screenshots when relevant, data/privacy impact, risks, and rollback approach.
7. Select **Create pull request**.
8. Wait for CI, resolve review comments, and request re-review after changes.

### GitHub CLI

If GitHub CLI is installed and authenticated:

```bash
gh pr create \
  --base develop \
  --head docs/professional-documentation \
  --title "docs: professionalize project documentation" \
  --body-file .github/pull_request_template.md
```

Do not submit an unedited empty template. Fill the actual context before using
`--body-file` or provide a prepared PR description file.

## Pull Request Review Standard

Reviewer verifies:

- scope matches the issue/proposal;
- module placement follows project boundaries;
- naming and API/data contracts are consistent;
- tests cover observable behavior and CI passes;
- no secret, raw dataset, model binary, or unrelated generated file is present;
- privacy, security, migration, and operational impacts are documented;
- README/docs reflect behavior changes;
- commit history is understandable.

At least one independent review is recommended before merge. Authors do not
resolve substantive review feedback without either implementing it or recording
a technical rationale.

## Merge Strategy

- Topic branch → `develop`: use squash merge for a noisy iterative history, or a
  merge commit when preserving multiple meaningful Conventional Commits matters.
- `develop` → `main`: use a release Pull Request and preserve an explicit merge
  boundary.
- `hotfix` → `main`: merge after urgent review, then synchronize the same change
  back to `develop`.

After merge:

```bash
git switch develop
git pull --ff-only origin develop
git branch -d <topic-branch>
git push origin --delete <topic-branch>
```

Delete topic branches only after confirming their commits are merged. Do not
delete long-lived `main` or `develop`.

## Release Synchronization

After a release Pull Request into `main`, ensure `develop` contains the release
merge commit:

```bash
git switch develop
git merge --ff-only main
git push origin develop
```

If fast-forward is impossible, inspect the graph and resolve divergence through
a reviewed merge. Do not use `git reset --hard` or force push to hide divergence.

## Recommended Repository Protection

- Require Pull Requests for `main` and `develop`.
- Require CI status checks.
- Prevent force pushes and branch deletion for long-lived branches.
- Require conversation resolution before merge.
- Require review approval when more than one contributor is available.
- Restrict secret and deployment-environment access by least privilege.

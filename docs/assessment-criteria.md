# LK02 Assessment Criteria and Evidence Matrix

This document maps the repository to the supplied LK02 rubric. It distinguishes
technical readiness from evidence that must still be captured in the submitted
report.

## Rubric Matrix

| Component | Weight | Rubric Indicator | Repository Evidence | Readiness | Remaining Submission Evidence |
| --- | ---: | --- | --- | --- | --- |
| Standardisasi Struktur | 30% | Folder follows best practices; naming convention consistent | `src/kuping_negara/`, data zones, tests, configs, docs, `.gitignore`, [Project Structure](project-structure.md), [Development Guidelines](development-guidelines.md) | Strong technical coverage | Screenshot repository tree and briefly explain `src` layout |
| Setup Codespaces | 30% | Environment runs without error; dependencies installed | `.devcontainer/devcontainer.json`, `requirements.txt`, `pyproject.toml`, `python -m kuping_negara.healthcheck` | Configured but remote execution evidence pending | Launch Codespace, capture successful `postCreateCommand`, health check, and test output |
| Branching Strategy | 20% | Informative commit history; appropriate branch usage | `main`, `develop`, topic branch workflow, Conventional Commits, PR template, [Git Workflow](git-workflow.md) | Strong technical coverage | Capture branch graph and informative commit/merge history; add PR evidence only if explicitly required by the lecturer |
| Dokumentasi README | 20% | Clear setup and system usage instructions | Root `README.md`: proposal, architecture, Quick Start, configuration, tests, workflow, roadmap, limits | Strong technical coverage | Capture rendered README and verify internal links in GitHub |

## Criterion Review

### 1. Standardisasi Struktur — 30%

Implemented evidence:

- one installable Python namespace under `src/kuping_negara`;
- separate ingestion, preprocessing, validation, labeling, training, inference,
  monitoring, API, and dashboard boundaries;
- separate raw, processed, and labeled data zones;
- unit and integration test directories;
- versioned configuration and data-contract directories;
- documented naming convention and code-placement decision guide;
- generated data, credentials, caches, and model artifacts excluded by
  `.gitignore`.

Assessment caution: empty package boundaries indicate planned ownership, not
implemented business capability. Explain this distinction during submission.

### 2. Setup Codespaces — 30%

Configured evidence:

- Python 3.12 Dev Container image;
- automatic dependency installation through `postCreateCommand`;
- Python, Jupyter, and GitLens extensions;
- project health check and unit test commands;
- CI reproduction of installation and test flow.

Required manual verification in GitHub Codespaces:

```bash
python --version
python -m kuping_negara.healthcheck
python -m pytest
git status
```

Full-credit evidence should show Python version, installed core dependencies,
passing tests, and a clean repository state inside the Codespace. A local-only
test does not prove Codespaces execution.

### 3. Branching Strategy — 20%

Implemented evidence:

- `main` used as stable/release branch;
- `develop` used as integration branch;
- work performed on purpose-specific topic branches;
- Conventional Commit types used in history;
- Pull Request template and documented review/cleanup workflow;
- merged topic branches deleted instead of kept permanently behind `main`.

The `ahead/behind` counter is not itself a grading objective. The direct rubric
indicator is demonstrated by correct base selection, reviewable commits,
meaningful merge history, and cleanup after merge. A Pull Request provides
stronger collaboration evidence, but it is not explicitly required by the
four-row indicator supplied for this assessment.

### 4. Dokumentasi README — 20%

README includes:

- project proposal, problem statement, research questions, and objectives;
- stakeholders, scope, requirements, deliverables, and risks;
- solution architecture and MLOps lifecycle;
- data and machine-learning strategies;
- Quick Start for Codespaces and local development;
- configuration, testing, Git workflow, monitoring, metrics, and roadmap;
- ethics, privacy, limitations, and project status.

## Screenshot Checklist

Capture these screenshots after the branch and Codespaces checks are complete:

1. GitHub repository root showing the standardized folder structure.
2. Rendered README showing proposal and Quick Start sections.
3. Codespaces creation page or running VS Code browser workspace.
4. Codespaces terminal showing `python -m kuping_negara.healthcheck` success.
5. Codespaces terminal showing all tests passing.
6. GitHub branch page showing `main` and `develop`.
7. Topic-branch commit history with informative Conventional Commits.
8. Optional: Pull Request into `develop`, including filled description and green
   checks, if collaboration evidence is requested.
9. Optional: release Pull Request from `develop` into `main` if required by the
   lecturer or final report format.
10. Project Board screenshot if LK02 submission instructions require it outside
    the four-row grading table.

## Current Conclusion

The repository has strong technical coverage for structure, branching policy,
and README documentation. Codespaces is configured correctly at repository
level, but the final submission should not claim complete verification until the
environment is launched successfully on GitHub and the required screenshots are
captured. Final scoring remains the assessor's decision.

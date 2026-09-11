## Summary

Describe the change in two or three precise sentences.

## Motivation

Explain the problem, requirement, or risk addressed by this Pull Request.

## Scope

- Included:
- Explicitly excluded:

## Change Type

- [ ] `feat`: new capability
- [ ] `fix`: bug fix
- [ ] `docs`: documentation only
- [ ] `test`: tests only
- [ ] `refactor`: internal change without behavior change
- [ ] `style`: formatting/whitespace only
- [ ] `chore`: maintenance, dependency, or configuration
- [ ] `ci`: CI/CD workflow

## Architecture and Data Impact

- Component(s) affected:
- Data contract/schema impact:
- Migration/backward compatibility:
- Security/privacy impact:

## Verification

List the exact commands and summarized results.

```bash
python -m kuping_negara.healthcheck
python -m pytest
```

## Evidence

Add logs, screenshots, metrics, or links required to independently verify the
change. Do not include credentials, cookies, tokens, or personal data.

## Risk and Rollback

- Primary risk:
- Detection method:
- Rollback procedure:

## Checklist

- [ ] Branch name follows `<type>/<kebab-case>`.
- [ ] Commit messages follow Conventional Commits.
- [ ] Change is limited to one coherent scope.
- [ ] Tests pass locally and CI is green.
- [ ] New/changed behavior has appropriate tests.
- [ ] Documentation and examples are updated.
- [ ] Data contract/configuration versions are updated when required.
- [ ] No secret, raw dataset, model binary, cache, or generated artifact is committed.
- [ ] Security, privacy, and operational impact has been reviewed.
- [ ] Reviewer can reproduce the verification steps.

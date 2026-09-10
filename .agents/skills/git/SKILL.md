---
name: git
description: Best practices for Git operations such as git clones commits, branches, and configurations.
---

# Git Best Practices Skill

This skill defines the Git workflow standards, commit message conventions, and environment configuration guidelines.

## 1. Git User Configuration

All automated, agentic, or CI/CD Git operations must use the standard non-interactive user identity. Ensure that before any commit or push action is performed, the following Git identity settings are applied:

- **Username**: `friendly-cicd-helper`
- **Email**: `duetai-webinar-presenters@google.com`

### Configuration Commands

Run these commands to establish the required git identity:

```bash
git config --global user.name "friendly-cicd-helper"
git config --global user.email "duetai-webinar-presenters@google.com"
```

---

## 2. Conventional Commits Standard (v1.0.0)

All commit messages must adhere strictly to the [Conventional Commits v1.0.0 specification](https://www.conventionalcommits.org/en/v1.0.0/).

### Commit Message Format

```text
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Commit Types

Use one of the following structural types to describe the intent of the commit:

| Type | Description |
| :--- | :--- |
| **feat** | A new feature for the codebase (corresponds to `MINOR` in semantic versioning). |
| **fix** | A bug fix (corresponds to `PATCH` in semantic versioning). |
| **docs** | Documentation-only changes. |
| **style** | Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc.). |
| **refactor** | A code change that neither fixes a bug nor adds a feature. |
| **perf** | A code change that improves performance. |
| **test** | Adding missing tests or correcting existing tests. |
| **build** | Changes that affect the build system or external dependencies (example scopes: gulp, broccoli, npm). |
| **ci** | Changes to CI configuration files and scripts (example scopes: Travis, Circle, GitHub Actions). |
| **chore** | Other changes that don't modify src or test files. |

### Structural Rules

1. **Commit Type**: Must be prefixed with a noun (e.g., `feat`, `fix`, etc.), followed by an optional scope, optional `!`, and a required colon and space.
2. **Scope**: Optional, placed within parentheses after the type (e.g., `feat(parser): add support for arrays`).
3. **Description**: A short summary of the code changes, written in imperative, present tense (e.g., "change" instead of "changed" or "changes").
4. **Breaking Changes**: Represented by a `!` after the type/scope or as a footer entry starting with `BREAKING CHANGE: ` (corresponds to `MAJOR` in semantic versioning).

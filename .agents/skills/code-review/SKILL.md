---
name: code-review
description: Guidelines, principles, checklists, and standards for conducting thorough and high-quality code reviews efficient at runtime.
---

# Code Review Skill

This skill outlines operational instructions, guidelines, and checklist items for conducting thorough, runtime-efficient code reviews.

---

## 1. Runtime Execution & Workflow Instructions

To conduct a thorough and efficient code review, execute a streamlined 3-step workflow without unnecessary file reading, API queries, re-diffing, or test execution:

1. **Repository Setup & Branch Checkout**:
   - Clone the repository, check out the PR branch, and get the HEAD commit SHA in a single command call:
     ```bash
     git clone https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git repo
     cd repo
     git fetch origin pull/${PR_NUMBER}/head:pr-${PR_NUMBER} && git checkout pr-${PR_NUMBER} && git rev-parse HEAD
     ```

2. **Single-Command Diff Inspection (Strict Lockfile & Asset Exclusion Across All Stacks)**:
   - Obtain and inspect the changeset in ONE unified command using pathspecs to exclude lockfiles and generated assets across all tech stacks (JS/Node, Python, Rust, Go, Ruby, PHP, Elixir, Dart, Java, Nix):
     ```bash
     git diff origin/main...HEAD -- . ':!*lock*' ':!package-lock.json' ':!npm-shrinkwrap.json' ':!yarn.lock' ':!pnpm-lock.yaml' ':!bun.lockb' ':!Cargo.lock' ':!Gemfile.lock' ':!poetry.lock' ':!Pipfile.lock' ':!mix.lock' ':!go.sum' ':!pubspec.lock' ':!composer.lock' ':!Composer.lock' ':!flake.lock' ':!*.min.js' ':!*.min.css' ':!*.map'
     ```
   - **Execution Efficiency & Context Guidelines**:
     - **Primary Source**: Rely on the unified `git diff` output as the primary source for evaluating changes.
     - **Targeted Context When Needed**: If understanding function callers, type definitions, or surrounding logic is necessary to ensure review accuracy, inspect *only* the specific line ranges or files directly linked to the diff using `view_file` (with precise line ranges).
     - **Prohibited Wasteful Patterns**:
       - Do NOT run `list_dir` to browse `/workspace/skills` subdirectories or repository folders (`/workspace/repo`, `repo/backend`).
       - Do NOT redirect `git diff` output to intermediate files (`diff.txt`) or create temporary payload files (`payload.json`).
       - Do NOT run `git diff --name-only`, `git branch -r`, or `git log`.
       - Do NOT issue `curl` REST API calls for PR metadata, and avoid running test suites (`vitest`, `jest`, `npm test`) unless explicitly requested.

3. **Submitting Review via GitHub CLI**:
   - Submit review findings directly using the GitHub CLI (`gh`):
     ```bash
     gh pr review "${PR_NUMBER}" --comment --body "Summary of findings..."
     ```
   - For line-specific comments, you can add comments or reviews directly using the `gh` CLI or GitHub API.

4. **Skill Integration & Extensibility**:
   - Feel free to load and combine any available or future workspace skills (such as `git`, domain-specific, or testing skills) as required by the code review task.

---

## 2. Principles of Code Review

Examine proposed diff changes systematically across the following dimensions:

### A. Correctness & Logic
- **Business Logic**: Does the modified code fulfill the target specification?
- **Edge Cases**: Verify boundary conditions, null/undefined checks, empty collections, and race conditions within modified paths.
- **Error Handling**: Ensure new logic catches, logs, and handles errors gracefully without crashing processes.

### B. Security & Vulnerability Analysis
- **Credential & Secret Leaks**: Scan modified lines for hardcoded API keys, passwords, certificates, or tokens.
- **Input Validation**: Verify that new inputs sanitization prevents SQL Injection, XSS, Command Injection, and Path Traversal.
- **Dependency Vulnerabilities**: Audit changes to package manifests (`package.json`, `pom.xml`, `requirements.txt`, etc.).

### C. Performance & Resource Efficiency
- **Complexity**: Identify nested loops ($O(N^2)$), N+1 queries, or resource leaks introduced in the diff.
- **Resource Management**: Ensure newly opened files, network streams, and DB sessions are properly closed (e.g., `with` statements, `try-with-resources`).

### D. Code Quality & Maintainability
- **Duplication & Readability**: Keep diff additions DRY and ensure functions/variables have descriptive names.
- **Documentation**: Verify inline comments in changed blocks explain the *why* clearly.

---

## 3. Standard Review Output Format

Output a structured summary categorizing findings:

| Category | Priority | Scope / Focus |
| :--- | :--- | :--- |
| **Security** | 🚨 Critical | Secrets, injection vulnerabilities, path traversal in diff changes. |
| **Correctness** | ⚠️ High | Logic bugs, unhandled edge cases, data race conditions in modified code. |
| **Performance**| 📈 Medium | Inefficient algorithms or resource leaks introduced in diff. |
| **Styling** | 🎨 Low | Readability, naming consistency, clean comments, formatting in diff. |

When referencing modified files or snippets in comments, include relative markdown links pointing directly to the file path and line numbers (e.g., `[filename](file:///path/to/file#L10-L20)`).

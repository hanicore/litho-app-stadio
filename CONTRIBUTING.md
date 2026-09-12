# Contributing to Litho Studio

Thank you for your interest in contributing to Litho Studio.

Litho Studio is an open-source project, and contributions are welcome. This document explains the basic workflow for contributing code, documentation, bug fixes, and improvements.

## Before You Start

Please check the existing GitHub issues before starting work.

If you want to work on a new idea, consider opening an issue first so the proposed change can be discussed before implementation.

## Development Setup

Clone the repository:

```bash
git clone https://github.com/hanicore/litho-app-stadio.git
cd litho-app-stadio
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python main.py
```

## Branches

Do not make changes directly on the `main` branch.

Create a separate branch for your work.

For a new feature:

```bash
git checkout main
git pull origin main
git checkout -b feature/short-description
```

For a bug fix:

```bash
git checkout main
git pull origin main
git checkout -b fix/short-description
```

For documentation changes:

```bash
git checkout -b docs/short-description
```

## Making Changes

Keep changes focused and easy to review.

Before committing, make sure that:

* The application starts correctly.
* Your changes do not unnecessarily affect unrelated parts of the project.
* Existing functionality still works.
* Documentation is updated when necessary.
* Temporary files and generated files are not committed.

## Commit Messages

Use short and descriptive commit messages.

Good examples:

```text
Fix STL export issue
Improve 3D preview
Update installation instructions
Fix image positioning
Add contribution documentation
```

Avoid vague messages such as:

```text
update
changes
fix
stuff
```

## Pull Requests

Push your branch to GitHub:

```bash
git push -u origin your-branch-name
```

Then open a Pull Request against the `main` branch.

A good Pull Request should explain:

1. What was changed.
2. Why the change was needed.
3. How the change was tested.
4. Any known limitations.

Please keep Pull Requests focused on one main purpose whenever possible.

## Bug Reports

When reporting a bug, include:

* A clear description of the problem.
* Steps to reproduce it.
* What you expected to happen.
* What actually happened.
* Your Python version.
* Your operating system.
* Relevant screenshots or error messages when available.

Use the provided GitHub bug report template whenever possible.

## Feature Requests

Before proposing a feature, check whether a similar request already exists.

A feature request should explain:

* What the feature should do.
* Why it would be useful.
* How it could improve the existing workflow.

Use the provided GitHub feature request template.

## Code Quality

Keep the code readable and maintainable.

Prefer:

* Clear variable and function names.
* Small, focused functions.
* Simple solutions over unnecessary complexity.
* Comments only where they provide useful context.

Avoid introducing dependencies unless they are actually needed.

## Respect the Existing Project

Litho Studio is intended to remain focused on its core purpose: creating and previewing printable lithophanes.

When contributing, avoid unrelated changes that significantly increase the project's complexity.

## Questions

If you are unsure about an implementation, open a GitHub issue or discuss the proposed change before doing a large amount of work.

Thank you for helping improve Litho Studio.

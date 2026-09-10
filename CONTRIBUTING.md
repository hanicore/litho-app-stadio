# 🤝 Contributing to Litho Studio

Thank you for your interest in contributing to **Litho Studio**!

Litho Studio is an open-source project focused on making image-to-lithophane creation simple, accessible, and enjoyable.

Whether you're fixing a bug, improving the interface, writing documentation, adding tests, or experimenting with new ideas, your contribution is welcome.

---

## 🌱 Ways You Can Contribute

You don't have to be an expert developer to contribute.

### 🐛 Report Bugs

Found something that doesn't work correctly?

Open an Issue and describe:

* What happened
* What you expected
* Steps to reproduce the problem
* Your operating system
* Your Python version
* Any error messages
* Screenshots when useful

---

### 💡 Suggest Improvements

Have an idea for Litho Studio?

Open an Issue and explain:

* What you would like to improve
* Why it would be useful
* How you think it could work

For large changes, please discuss the idea before starting development.

---

### 📚 Improve Documentation

Documentation contributions are always useful.

You can help improve:

* README
* Installation instructions
* Tutorials
* Code comments
* Examples
* Troubleshooting guides

---

### 🧪 Add Tests

Tests help keep Litho Studio reliable.

You can contribute tests for:

* Image processing
* Heightmap generation
* Mesh generation
* STL export
* Settings
* Other core functionality

---

### 🎨 Improve the UI

If you have experience with PySide6 or UI design, you can help improve:

* Layout
* Usability
* Accessibility
* Visual consistency
* User feedback
* Error messages

---

## 🚀 Getting Started

### 1. Fork the Repository

Create your own fork of the Litho Studio repository on GitHub.

### 2. Clone Your Fork

```bash
git clone https://github.com/YOUR-USERNAME/litho-app-stadio.git
cd litho-app-stadio
```

### 3. Create a Virtual Environment

```bash
python -m venv .venv
```

### 4. Activate It

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Run Litho Studio

```bash
python main.py
```

---

## 🌿 Create a Branch

Please create a separate branch for your work.

For a new feature:

```bash
git checkout -b feature/short-description
```

For a bug fix:

```bash
git checkout -b fix/short-description
```

For documentation:

```bash
git checkout -b docs/short-description
```

Example:

```bash
git checkout -b fix/image-processing-error
```

---

## 💻 Make Your Changes

Keep your changes focused.

A Pull Request should ideally solve **one problem at a time**.

Before submitting your work:

* Test your changes
* Check for obvious errors
* Keep the code readable
* Avoid unrelated changes
* Update documentation when necessary

---

## 🧪 Test Your Changes

Run Litho Studio and make sure the affected functionality works correctly.

If you add or modify functionality that can be tested automatically, please consider adding a test.

---

## 📝 Commit Your Changes

Use a clear commit message.

Examples:

```bash
git add .
git commit -m "Fix image processing error"
```

```bash
git commit -m "Improve lithophane preview"
```

```bash
git commit -m "Update installation documentation"
```

Try to explain **what changed**, rather than writing messages such as:

```text
update
changes
fixed stuff
final
```

---

## 📤 Push Your Branch

```bash
git push -u origin your-branch-name
```

Example:

```bash
git push -u origin fix/image-processing-error
```

---

## 🔀 Open a Pull Request

Go to the Litho Studio repository on GitHub and open a Pull Request.

Your Pull Request should explain:

### What changed?

Briefly describe your changes.

### Why?

Explain the problem or motivation.

### Testing

Explain how you tested the changes.

### Related Issue

If your Pull Request fixes an Issue, mention it.

Example:

```text
Closes #15
```

---

## 🏷️ Good Issues for New Contributors

If you're new to the project, look for Issues with labels such as:

* `good first issue`
* `help wanted`
* `documentation`
* `bug`
* `enhancement`

These are good starting points.

---

## ⚠️ Before Opening a Pull Request

Please check:

* [ ] The project runs correctly
* [ ] My changes solve the intended problem
* [ ] I tested the affected functionality
* [ ] I did not include unrelated changes
* [ ] I updated documentation if necessary
* [ ] My commit messages are clear
* [ ] I explained my changes in the Pull Request

---

## 🤖 AI-Assisted Contributions

AI coding tools may be used to help understand code, brainstorm solutions, or write code.

However, contributors are responsible for understanding and reviewing the code they submit.

Please make sure that:

* You understand your changes
* You test generated code
* You check for bugs
* You respect the project's license
* You do not submit generated code that you cannot explain or maintain

AI should assist the contributor, not replace responsible development.

---

## 🧭 Development Philosophy

Litho Studio aims to remain:

* 🧩 Simple
* 🛠️ Maintainable
* 📖 Understandable
* 🖥️ User-friendly
* 🌱 Open to contributors

Large changes should be discussed before implementation whenever possible.

---
## 🧊 3D Preview

One of the project's goals is to develop a professional and reliable 3D preview experience.

The 3D preview should aim to provide:

* Smooth camera controls
* Rotate, zoom, and pan
* Accurate visualization of the generated lithophane
* Clear lighting and depth representation
* Professional rendering quality
* Responsive interaction
* Correct model proportions and dimensions
* Reliable rendering without visual artifacts
* A clean and modern presentation

Contributors working on the 3D preview should prioritize **visual accuracy, stability, performance, and usability**.

The goal is to make the preview feel like a professional 3D tool while keeping Litho Studio accessible and easy to use.



## ❤️ Thank You

Every contribution matters.

A bug report, documentation fix, test, design improvement, or code contribution can help make Litho Studio better.

Thank you for helping build Litho Studio! 🖼️

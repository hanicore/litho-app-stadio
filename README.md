# 🖼️ Litho Studio

> **Turn your images into printable 3D lithophanes.**

**Litho Studio** is a free, open-source desktop application built with **Python** and **PySide6** for creating 3D-printable lithophanes from ordinary images.

Transform a 2D image into a physical object where light reveals the hidden details of the picture.

<p align="center">
  <strong>Image → Heightmap → 3D Mesh → STL → 3D Print</strong>
</p>

---

## ✨ Features

* 🖼️ Convert images into 3D lithophanes
* ⚙️ Adjustable lithophane thickness
* 📐 Control physical dimensions in millimeters
* 🌓 Grayscale-based depth generation
* 🔄 Image flipping and mirroring
* ✂️ Image cropping and positioning
* 🧱 Generate printable 3D geometry
* 💡 Preview how light interacts with the lithophane
* 🧊 3D preview of the generated model
* 📦 Export models as `.STL`
* 🖥️ Modern desktop interface
* 🐍 Built with Python
* 🌱 Open-source and community-friendly

---

## 🎯 What is a Lithophane?

A lithophane is a thin 3D object whose thickness varies according to an image.

When light passes through it, different thicknesses produce different levels of brightness, revealing the image.

```text
        IMAGE
          │
          ▼
   ┌───────────────┐
   │  Grayscale    │
   │   Heightmap   │
   └───────┬───────┘
           │
           ▼
    ┌─────────────┐
    │  3D Mesh    │
    └──────┬──────┘
           │
           ▼
       STL FILE
           │
           ▼
      3D PRINT 🖨️
           │
           ▼
      💡 LIGHT
           │
           ▼
       🖼️ IMAGE
```

---

## 🧰 Built With

| Technology           | Purpose                      |
| -------------------- | ---------------------------- |
| 🐍 Python            | Core application logic       |
| 🎨 PySide6           | Desktop GUI                  |
| 🖼️ Image Processing | Image → heightmap conversion |
| 🧊 3D Geometry       | Mesh generation              |
| 📦 STL               | 3D-printable model export    |
| 🔧 Git               | Version control              |
| 🐙 GitHub            | Open-source development      |

---

## 🚀 Getting Started

### Requirements

* Windows
* Python 3.13+
* Git
* A supported Python environment

### 1. Clone the repository

```bash
git clone https://github.com/hanicore/litho-app-stadio.git
```

### 2. Enter the project directory

```bash
cd litho-app-stadio
```

### 3. Create a virtual environment

```bash
python -m venv .venv
```

### 4. Activate the environment

**Windows PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
```

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

### 6. Run Litho Studio

```bash
python main.py
```

---

## 🖥️ How It Works

Litho Studio follows a simple pipeline:

```text
                    ┌──────────────┐
                    │    Image     │
                    └──────┬───────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Image Processing│
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   Heightmap     │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Mesh Generator │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   3D Preview    │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   STL Export    │
                  └────────┬────────┘
                           │
                           ▼
                    🖨️ 3D Printing
```

---

## 📁 Project Structure

```text
litho-app-stadio/
│
├── main.py
├── core.py
├── requirements.txt
├── README.md
├── LICENSE
│
├── assets/
│
├── shaders/
│
└── .github/
    └── workflows/
```

> The project structure may evolve as Litho Studio grows.

---

## 🧪 Development

Litho Studio is actively being developed.

Before making changes, create a new branch:

```bash
git checkout -b feature/your-feature
```

Make your changes, test them, and then commit:

```bash
git add .
git commit -m "Add your change"
```

Push your branch:

```bash
git push -u origin feature/your-feature
```

Then open a Pull Request on GitHub.

---

## 🤝 Contributing

Contributions are welcome!

You can contribute by:

* 🐛 Reporting bugs
* 💡 Suggesting improvements
* 🧪 Adding tests
* 📚 Improving documentation
* 🎨 Improving the user interface
* ⚡ Improving performance
* 🧊 Improving 3D generation
* 🤖 Working on open-source AI features
* 🔧 Fixing existing issues

Please read the project's `CONTRIBUTING.md` before submitting a Pull Request.

For larger changes, open an Issue first so the idea can be discussed before implementation.

---

## 🏷️ Good First Issues

New contributors are welcome.

Look for issues labeled:

```text
good first issue
help wanted
documentation
enhancement
bug
```

These are good places to start contributing to Litho Studio.

---

## 🌱 Open Source

Litho Studio is developed openly on GitHub.

The goal is not simply to create another image-to-STL converter.

The goal is to build a **simple, modern, accessible lithophane tool** that people can learn from, use, improve, and contribute to.

---

## 🗺️ Roadmap

### 🟢 Current

* [x] Image processing
* [x] Heightmap generation
* [x] STL generation
* [x] Adjustable dimensions
* [x] Thickness controls
* [x] 3D preview
* [x] Light simulation
* [x] Open-source repository

### 🟡 In Progress

* [ ] More automated tests
* [ ] Documentation improvements
* [ ] Performance improvements
* [ ] Better error handling
* [ ] Contributor documentation

### 🔵 Future

* [ ] More advanced 3D preview
* [ ] Additional lithophane geometries
* [ ] Improved lighting simulation
* [ ] More image-processing controls
* [ ] Open-source AI-assisted features
* [ ] Community-driven improvements

---

## 📸 Screenshots

Screenshots and demonstrations will be added as the interface continues to evolve.

```text
Coming soon...
```

---

## 🐛 Bug Reports

Found a bug?

Please open a GitHub Issue and include:

* What happened
* What you expected to happen
* Steps to reproduce the problem
* Python version
* Operating system
* Relevant screenshots or error messages

The more information you provide, the easier it is to reproduce and fix the problem.

---

## 💬 Community

Have an idea for Litho Studio?

Open an Issue or start a discussion on GitHub.

Whether you're a Python beginner, 3D-printing enthusiast, developer, designer, or just curious about lithophanes, contributions and ideas are welcome.

---

## 👨‍💻 Maintainer

**Hani**

GitHub: [@hanicore](https://github.com/hanicore)

Litho Studio started as a learning project and is evolving into a real open-source application.

---

## 📄 License

Litho Studio is open-source software.

See the [`LICENSE`](LICENSE) file for the full license information.

---

## ⭐ Support the Project

If you find Litho Studio useful:

⭐ Star the repository
🐛 Report bugs
💡 Suggest ideas
🔧 Contribute code
📚 Improve documentation
📢 Share the project

Every contribution helps move the project forward.

---

<p align="center">

### 🖼️ From pixels to light.

**Litho Studio**

Made with 🐍 Python, ☕ curiosity, and a lot of debugging.

</p>

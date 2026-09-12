# Litho Studio

Litho Studio is a free, open-source desktop application for creating printable lithophanes from images.

The project is built with Python and PySide6 and is designed to provide a simple workflow for turning an image into a 3D lithophane model that can be exported for 3D printing.

## Features

* Convert images into 3D lithophane models
* Adjust lithophane thickness
* Set model dimensions in millimeters
* Generate grayscale-based depth information
* Flip and mirror images
* Crop and position the source image
* Preview the result in 3D
* Preview image and lighting interaction
* Export models as STL
* Modern desktop interface built with PySide6

## Requirements

* Windows
* Python 3.13 or newer
* PySide6

Python 3.14 is also supported in the current development environment.

## Installation

Clone the repository:

```bash
git clone https://github.com/hanicore/litho-app-stadio.git
cd litho-app-stadio
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python main.py
```

## Project Structure

```text
litho-app-stadio/
|
|-- main.py
|-- core.py
|-- requirements.txt
|-- README.md
|-- CONTRIBUTING.md
|-- LICENSE
|
`-- .github/
    |-- pull_request_template.md
    `-- ISSUE_TEMPLATE/
        |-- bug_report.md
        `-- feature_request.md
```

## Development

Litho Studio is currently under development.

Before making changes, create a new branch from `main`:

```bash
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

For bug fixes:

```bash
git checkout -b fix/your-fix-name
```

After making your changes:

```bash
git status
git add .
git commit -m "Describe your changes"
git push -u origin your-branch-name
```

Then open a Pull Request on GitHub.

## Contributing

Contributions are welcome.

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a Pull Request.

Bug reports and feature requests can also be submitted through the GitHub issue templates.

## Repository

GitHub:
https://github.com/hanicore/litho-app-stadio

## Maintainer

Hani
GitHub: https://github.com/hanicore

## License

See the [LICENSE](LICENSE) file for the license and usage terms.

## Project Status

Litho Studio is an active development project.

The current focus is improving the existing application, refining the user interface, improving the preview experience, and making the project easier for other developers to understand and contribute to.

New contributors are encouraged to check the open GitHub issues before starting work.
 
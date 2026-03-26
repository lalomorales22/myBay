# Contributing to myBay

Thanks for your interest in contributing! Here's how to get started.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/mybay.git`
3. Create a branch: `git checkout -b my-feature`
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and add your API keys

## Development

- Run the app: `python run.py`
- Run tests: `python -m pytest tests/`
- Run a specific test phase: `python -m pytest tests/test_phase1.py -v`

## Submitting Changes

1. Make your changes and add tests if applicable
2. Run the full test suite to make sure nothing broke
3. Commit with a clear message describing the change
4. Push to your fork and open a Pull Request

## Reporting Issues

- Use GitHub Issues for bugs and feature requests
- Include steps to reproduce for bugs
- Include your OS and Python version

## Code Style

- Follow existing patterns in the codebase
- Keep functions focused and well-named
- Add docstrings for new modules and classes

# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in myBay, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities.
2. Email the maintainer directly (see the commit history for contact info).
3. Include a description of the vulnerability, steps to reproduce, and any potential impact.

We will acknowledge receipt within 48 hours and aim to release a fix within 7 days for critical issues.

## Scope

myBay is a desktop application that runs a local web server on your LAN. Security considerations include:

- **Local server endpoints** are accessible to anyone on your local network.
- **eBay OAuth tokens** are stored locally in `~/.ebay_config.json` with `0600` permissions.
- **OpenAI API keys** are stored in your `.env` file (never committed to git).
- **Product images** are sent to OpenAI's API for analysis (or processed locally with Ollama).

## Best Practices for Users

- Never commit your `.env` file or `.ebay_config.json` to version control.
- Run the app only on trusted networks.
- Keep your dependencies up to date: `pip install --upgrade -r requirements.txt`

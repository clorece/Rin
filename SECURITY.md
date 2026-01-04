# Security Policy

## Supported Versions

Use the latest version of Rin to ensure you have the most recent security updates.

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |
| Old     | :x:                |

## Reporting a Vulnerability

We take the security of Rin seriously. If you discover a security vulnerability, please follow these steps:

1.  **Do NOT** open a public issue immediately if the vulnerability allows for remote exploitation or data exfiltration.
2.  Please report the issue via the **GitHub Security Tab** (if enabled) or contact the maintainer directly.
3.  If no private channel is clear, please open an Issue with the tag `security` and provide a high-level description without revealing exploit details.

## Data Privacy & Architecture

Rin is built with a **Local-First** philosophy to maximize user privacy:

*   **Local Storage**: All screenshots, audio buffers, logs, and database files (`rin.db`, `long_term_memory.json`) are stored locally on your machine.
*   **No Telemetry**: We do not collect usage data or send telemetry to third-party servers (other than the necessary API calls to Google Gemini).
*   **API Usage**: Data sent to the LLM Provider (Google Gemini) is subject to their configured privacy policies.

## Best Practices for Users

*   **Protect your API Key**: Your `GEMINI_API_KEY.txt` grants access to the AI model. **Never** share this file or commit it to a public repository.
*   **Review Logs**: Your `logs/backend.log` may contain transcribed text or system paths. Review it before sharing for debugging.
*   **Updates**: Regularly pull the latest changes from the repository to ensure you have the latest fixes.

# Rin - AI Desktop Companion

> An edge intelligence companion for your personal computer.

<div align="center">
  <img src="frontend/src/assets/rin-showcase.jpg" alt="Rin Profile Picture" width="500"/>
  <br>
  <sub>Image used for profile picture by @daisukerichard on x! Please see credits below!</sub>
</div>
<br />

Rin is an intelligent, **visually and audio-aware** desktop companion designed to quietly support your digital life. She observes your screen, hears your system audio, and understands your context, offering guidance or company when you need it. **She learns from your interactions**, becoming smarter and more personalized with every session. **All your data and memories are stored locally on your machine**, ensuring your privacy and security.

### Rin is currently to be under a replanning phase as I have switched to linux and will temporary put windows support on hold until I get dual booting to work. Please expect a lot of issues with the current commit of Rin

## Getting Started

### Prerequisites
*   Windows 10/11
*   Python 3.10+
*   Node.js & npm
*   [Ollama](https://ollama.com/download) (local LLM runtime)
*   GPU with Vulkan support recommended (AMD, NVIDIA, or Intel)

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/clorece/rin.git
    cd rin
    ```

2.  **Install Ollama**:
    Download and install from [ollama.com/download](https://ollama.com/download)

3.  **Run Setup**:
    Double-click `setup.bat`. This will:
    *   Create a Python virtual environment for the backend.
    *   Install Python dependencies.
    *   Install Node.js dependencies for the frontend.
    *   Download required Ollama models (gemma3:4b for chat, moondream for vision).

    > **Important Note:**
    > Unfortunately setup.bat is currently bugged, if you are updating or installing Python or Node.js please restart immediately after setup.bat,
    > then relaunch the setup batch file after restart to finishes the install for those, otherwise you will keep looping on the installation.
    > This may force you to do more than 1 restart and setup initializations.
    > I know this is not ideal, and will make a fix for it as soon as possible.

### Usage

*   **Start Rin**: Double-click **`start.bat`**.
    *   This launches Rin with GPU acceleration (Vulkan).
*   **Debug Mode**: If you need to see logs or troubleshoot, use `debug.bat`.
*   **Shutdown**: Click the Power button in the Rin header to cleanly shut down both the UI and the background brain.

## Personalization

You can inform Rin about yourself by editing `user_profile.txt` in the root directory:
```text
Username=YourName
DateOfBirth=January 1
Interests=Coding, Gaming, Sci-Fi
Dislikes=Spiders, Lag
```

## Reporting Issues

If you encounter any bugs or issues, please report them via the **[GitHub Issues](https://github.com/clorece/rin/issues)** tab.

**When reporting a bug, please:**
1.  Describe the issue clearly.
2.  **Attach a Screenshot** of the error or issue if possible.
3.  **Attach relevant logs** from the `logs/` folder:
    *   **`error.log`**: For crashes or critical errors (Most Important).
    *   **`backend.log`**: For general system status.
    *   **`api_usage.log`**: If the issue relates to Rin not seeing/hearing.
    *   *(Note: Logs are auto-cleared on Rin's startup, so, if you have already restarted Rin before reading or uploading the logs, please reproduce the bug and then upload the logs immediately.)*
4.  Include steps to reproduce the problem.

## Credits

**Profile Picture Art**:
By **[@daisukerichard](https://x.com/daisukerichard)**
*   [Original Post](https://x.com/daisukerichard/status/1535913944262803456?s=20)

If you are the original owner of credited work and assets, and would like credit adjustments or removal of assets from the project, please feel free to contact me through github.

**Development**:
Built with Electron, React, FastAPI, and Ollama.

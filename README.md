# FQS (Fedora Quick Start)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Bash](https://img.shields.io/badge/Language-Bash-4EAA25.svg)](https://www.gnu.org/software/bash/)
[![Fedora](https://img.shields.io/badge/OS-Fedora-294172.svg?logo=fedora)](https://fedoraproject.org/)

Fedora Quick Start is an interactive, TUI-driven post-installation script to get your fresh Fedora system set up, hardened, and ready for daily use.

If [Secureblue](https://secureblue.dev) is a bit too "hardcore" for you, but you still want a solid, secure, and performant base, this script might be enough for you.

<img src="real+fax.jpeg" width="550" height="350" alt="real fax">

## Features

The script uses a standard Whiptail terminal interface. You just check off the features you want upfront, hit enter, and the script will handle the rest unattended.

### Core System
* **Updates:** Performs a full system upgrade.
* **Repositories:** Enables RPM Fusion (Free/Non-Free) and Flathub.
* **DNF Optimization:** Configures `dnf.conf` for parallel downloads, caching, and better speed.
* **Automation:** Optionally sets up `dnf-automatic` for silent security updates.

### Hardening & Privacy
* **Kernel & Network:** Applies Secureblue-inspired sysctl hardening, randomizes MAC addresses, and sets Firewalld to DROP.
* **Hardcore Kernel Hardening Args** Applies "Hardcore" kernel hardening.
* **Physical Security:** Installs and enables `usbguard` and `fail2ban`.
* **Secure Boot:** Creates and enrolls custom Secure Boot keys via `sbctl`.
* **Tor & VPNs:** Easily install the Tor daemon/browser, IVPN, or Mullvad.

### Gaming & Software
* **Gaming:** Installs Steam along with the latest Proton-GE release.
* **Windows Apps:** Installs [WinBoat](https://github.com/TibixDev/winboat) for seamless Windows app support via Podman.
* **Browsers:** Choose between Helium, Trivalent, Brave (auto-debloated), Chromium, or Librewolf.
* **Custom Software:** Prompt to install any extra DNF or Flatpak packages you need.

### Developer & Quality of Life
* **Dev Tools:** Installs essential tools (Git, Node, Go, Python, etc.) and your choice of editor (Zed, VSCodium, or NeoVim+NvChad).
* **Git/SSH:** Automatically generates SSH keys and sets up your global Git config.
* **Bash Prompt:** Installs a clean, custom bash prompt showing Git branches and current directories.
* **Hardware Tweaks:** Patches Apple keyboard fn keys and adds Dracut flags for Bluetooth keyboard support during LUKS decryption.

---

## Run

You can run this script with a single command without downloading it manually:

```bash
sh -c "$(curl -sS https://raw.githubusercontent.com/vil/fqs/master/fqs)"
```

## Installation
If you prefer to clone the repository and review the code locally before running:

Clone the repository:

```Bash
git clone https://github.com/vil/fqs.git && cd fqs
```

Make the script executable:

```Bash
chmod +x fqs
```

Run the script:

```Bash
./fqs
```

## Contributing
If you are a Fedora user and want to improve this, feel free to open a pull request.

## Credits
[Secureblue](https://secureblue.dev) for their hardening configurations.

## License
This source code is under the GNU General Public License, version 3.

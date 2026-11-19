# FQS (Fedora Quick Start)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Bash](https://img.shields.io/badge/Language-Bash-4EAA25.svg)](https://www.gnu.org/software/bash/)
[![Fedora](https://img.shields.io/badge/OS-Fedora-294172.svg?logo=fedora)](https://fedoraproject.org/)

Fedora Quick Start is an interactive, TUI-driven post-installation script to get your fresh Fedora system set up, hardened, and ready for daily use.

If [Secureblue](https://secureblue.dev) is a bit too "hardcore" for you, but you still want a solid, secure, and performant base, this script might be enough for you.

<img src="real+fax.jpeg" width="550" height="350" alt="real fax">

## Features

The script uses a Whiptail terminal interface. Open a category, select an option to read its effects and risks, then enable or disable it in your plan. Only system updates are selected initially. Review the complete plan before explicitly applying it; Back lets you change your choices. SSH key generation may ask for a passphrase during execution.

### Core System
* **Updates:** Performs a full system upgrade.
* **Repositories:** Enables RPM Fusion (Free/Non-Free), Flathub and Terra repositories.
* **DNF Settings:** Adds missing parallel-download, signature-checking and cleanup settings without overriding existing values.
* **Automation:** Optionally sets up `dnf-automatic` for silent security updates.

### Hardening & Privacy
* **Kernel & Network:** Applies Secureblue-inspired sysctl hardening, randomizes MAC addresses, disables hostname sending, disables GeoClue, and sets Firewalld to DROP.
* **Kernel Hardening Args:** Applies opt-in arguments to the default kernel via grubby, backs up boot entries, and requires another installed kernel for recovery.
* **Strict Flatpak Overrides:** Revokes overly broad filesystem and device permissions globally, and installs Flatseal so you can selectively re-enable access per app.
* **Secure DNS (DoT):** Configures strict DNS-over-TLS via `systemd-resolved` with Cloudflare, Quad9, AdGuard, or custom servers. Explains and lets you choose DNSSEC `yes` (default) or `allow-downgrade`; see the tradeoffs below.
* **Filesystem Security:** Optionally blocks uncommon filesystem modules (`cramfs`, `freevxfs`, `jffs2`, `hfs`, `hfsplus`), refusing if they are mounted or listed in `fstab`. Common local, optical and network filesystems remain available.
* **Physical Security:** Installs and enables `usbguard` and `fail2ban`.
* **Secure Boot Safety:** Does not automatically enroll firmware keys. Prepare recovery and a verified signed boot chain manually; NVIDIA installation is refused on EFI systems when Secure Boot is enabled or cannot be checked.
* **Tor & VPNs:** Easily install the Tor daemon/browser, IVPN, or Mullvad.

### Gaming & Software
* **Gaming:** Installs Steam along with the latest Proton-GE release.
* **Virtualization:** Installs virt-manager for managing virtual machines.
* **Browsers:** Choose between Helium, Trivalent, Brave (auto-debloated), Chromium, or Librewolf.
* **Custom Software:** Prompt to install any extra DNF or Flatpak packages you need.

### Developer & Quality of Life
* **Dev Tools:** Installs essential tools (Git, Node, Go, Python, etc.) and your choice of editor (Zed, VSCodium, or NeoVim+NvChad).
* **Git/SSH:** Sets missing Git identity values and generates an SSH key with an interactive passphrase prompt, without overwriting existing identities or keys.
* **Bash Prompt:** Installs a clean, custom bash prompt showing Git branches and current directories.
* **Hardware Tweaks:** Configures Apple keyboard function keys and optional Bluetooth support for future initramfs builds. Existing boot images are not automatically rebuilt.

---

## Safety and existing configuration

Run as a normal user on a writable, systemd-based Fedora installation, using Bash and a terminal of at least 80×24. Immutable/OSTree systems and root execution are rejected. `sudo`, Python 3 and curl must be installed; if Whiptail is missing, the script asks before installing `newt`.

* **Keep existing files** is the default policy. Conflicting settings are skipped and reported, not silently overwritten. Packages and explicitly selected service changes may still run.
* **Back up and replace** saves replaced system configurations under `/var/backups/fqs/<run>/` before writing them. Bash prompt backups live next to `.bashrc`. Existing SSH keys, Git identity and Neovim configs remain protected regardless of policy.
* Configuration writes are staged before replacement; symlink destinations are refused. Identical files are left unchanged.
* Network/device-disabling actions are opt-in and blocked over SSH. FQS does not restart NetworkManager. Read each option's compatibility and recovery notes before enabling it.
* Execution stops on failure and reports the current action. **Earlier changes are not automatically rolled back.** Configuration backups do not reverse package, service, permission, firmware or every boot change.

### DNSSEC choice

The secure DNS wizard explains these options before asking you to choose, and includes the selected mode in the final review:

| Mode | Behavior and tradeoff |
| --- | --- |
| `yes` **(default)** | Enforces DNSSEC validation. Invalid signatures are rejected; DNS lookups can fail when the resolver or network cannot support DNSSEC. Unsigned domains can still resolve—this does not require every domain to be signed. |
| `allow-downgrade` | Validates when support is detected, but allows validation to be disabled when the resolver appears not to support it. More compatible, but an attacker may be able to trigger that downgrade and remove DNSSEC protection. |

DNSSEC authenticates signed DNS data; DNS-over-TLS encrypts the connection to your chosen resolver. **`DNSOverTLS=yes` remains strict with either DNSSEC choice.** Secure DNS requires `/etc/resolv.conf` to already use the systemd-resolved stub; FQS will not replace it. Local/VPN DNS and captive portals may need manual configuration.

## Run

Reviewing a local copy before running is recommended. To run without cloning:

```bash
bash -c "$(curl -fsS https://raw.githubusercontent.com/vil/fqs/master/fqs)"
```

## Installation
If you prefer to clone the repository and review the code locally before running:

Clone the repository:

```bash
git clone https://github.com/vil/fqs.git && cd fqs
```

Make the script executable:

```bash
chmod +x fqs
```

Run the script:

```bash
./fqs
```

## Validation

Offline regression tests mock system operations and do not install packages or modify system configuration:

```bash
bash -n fqs
python3 -m unittest discover -s tests -v
shellcheck fqs
```

Actual package installation, hardware compatibility, firmware behavior and desktop integration still need testing in a disposable Fedora VM before use on an important machine.

## Contributing
If you are a Fedora user and want to improve this, feel free to open a pull request.

## Credits
[Secureblue](https://secureblue.dev) for their hardening configurations.

## License
This source code is under the GNU General Public License, version 3.

# fqs
Fedora Quick Start, a script to finish your post-installation and hardening steps easily.

<img src="real+fax.jpeg" width=550px height=350px>

Steps the script does:
1. Updates and upgrades the system.
2. Setup automatic updates using dnf-automatic.
3. Enables RPM Fusion repositories for additional software.
4. Enables Flathub repositories for flatpak packages.
5. Configures dnf to speed up package management.
6. Installs Nvidia drivers if an Nvidia GPU is detected.
7. Patches bluetooth and keyboard settings.
8. Installs a trusted VPN app.
9. Installs a list of user-specified software.
10. Install WinBoat for Windows app support.
11. Installs a custom Bash prompt.
12. Applies some **hardening** for your system.
13. Create and enroll Secure Boot keys.

all steps require user confirmation, so you can choose yourself what to do.


## Run
You can run this script simply with one line without installing anything:

`sh -c "$(curl -sS https://raw.githubusercontent.com/vil/fqs/master/fqs)"`

Or you can follow the installation steps below.

## Installation
1. Clone the repository `git clone https://github.com/vil/fqs.git && cd fqs`
2. Make the script runnable `chmod +x fqs`
3. Run the script `./fqs`

## Contributing
If you are a Fedora user and want to improve this, just feel free to open up a pull request :)

-----------------------------
## License
> [This source code is under the GNU General Public License, version 3.](https://www.gnu.org/licenses/gpl-3.0.txt)

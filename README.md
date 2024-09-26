# fqs
Fedora Quick Start, a script to finish your post-installation steps easily.

Steps the script does:
1. Updates and upgrades the system.
2. Enables RPM Fusion repositories for additional software.
3. Enables Flathub repositories for flatpak packages.
4. Configures dnf to speed up package management.
5. Installs Nvidia drivers if an Nvidia GPU is detected.
6. Patches bluetooth and keyboard settings.
7. Installs a list of user-specified software.
8. Sets up zsh shell with oh-my-zsh.

all steps require user confirmation, so you can choose yourself what to do.


## Run
You can run this script simply with one line without installing anything:

`sh -c "$(curl -sS https://codeberg.org/vili/fqs/raw/branch/master/fqs)"`

Or you can follow the installation steps below.

## Installation
1. Clone the repository `git clone https://codeberg.org/vili/fqs.git && cd fqs`
2. Make the script runnable `chmod +x fqs`
3. Run the script `./fqs`

## Contributing
If you are a Fedora user and want to improve this, just feel free to open up a pull request :)

-----------------------------
## License
> [This source code is under the GNU General Public License, version 3.](https://www.gnu.org/licenses/gpl-3.0.txt)

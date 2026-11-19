"""Offline regression tests for the sourceable Bash helpers in fqs."""

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "fqs"
BASH = shutil.which("bash")


@unittest.skipUnless(BASH, "Bash is required")
class FqsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fqs-tests-")
        self.addCleanup(self.temp.cleanup)
        self.sandbox = Path(self.temp.name)
        self.bin_dir = self.sandbox / "bin"
        self.bin_dir.mkdir()
        # An allowlist prevents an unexpected call from reaching system tools.
        for name in (
            "python3", "cat", "mktemp", "cmp", "install", "dirname", "cp", "mv"
        ):
            executable = shutil.which(name)
            if executable is None:
                self.skipTest(f"Required test tool is unavailable: {name}")
            (self.bin_dir / name).symlink_to(executable)
        self.env = {
            "PATH": str(self.bin_dir),
            "HOME": str(self.sandbox),
            "TMPDIR": str(self.sandbox),
            "LC_ALL": "C",
        }

    def bash(self, code, *args, before_source=""):
        # Never inherit BASH_ENV, exported functions, or the user's shell setup.
        program = r'''
set -euo pipefail
blocked() { printf 'Unexpected external action: %s\n' "$*" >&2; exit 97; }
sudo() { blocked sudo "$@"; }
whiptail() { blocked whiptail "$@"; }
systemctl() { blocked systemctl "$@"; }
dnf() { blocked dnf "$@"; }
rpm() { blocked rpm "$@"; }
curl() { blocked curl "$@"; }
wget() { blocked wget "$@"; }
''' + before_source + '\nsource "$1"\nshift\n' + code
        assert BASH is not None
        return subprocess.run(
            [BASH, "--noprofile", "--norc", "-c", program, "fqs-test", str(SCRIPT),
             *(str(arg) for arg in args)],
            cwd=REPO_ROOT,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )

    def assert_success(self, result):
        self.assertEqual(
            result.returncode, 0,
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_source_has_no_runtime_side_effects(self):
        result = self.bash(
            r'''
[[ "$PWD" == "$original_pwd" ]]
[[ "$(trap -p)" == "$original_traps" ]]
[[ -z "$(jobs -pr)" ]]
[[ -z "$WORK_DIR" && -z "$SUDO_PID" && -z "$BACKUP_DIR" ]]
[[ "$CONFIG_POLICY" == keep && "$CONFIG_CHANGED" == false && "$CONFIG_READY" == false ]]
[[ ${#OPTION_IDS[@]} == 0 ]]
declare -F main choose_dnssec enable_secure_dns write_config >/dev/null
''',
            before_source=r'''
original_pwd="$PWD"
trap ':' EXIT
original_traps=$(trap -p)
mktemp() { blocked mktemp "$@"; }
install() { blocked install "$@"; }
''',
        )
        self.assert_success(result)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertEqual(list(self.sandbox.iterdir()), [self.bin_dir])

    def test_choose_dnssec_arguments_explanations_and_stderr_selection(self):
        for dimensions in ((), (30, 100)):
            for selection in ("yes", "allow-downgrade"):
                with self.subTest(dimensions=dimensions, selection=selection):
                    arguments = self.sandbox / "whiptail-args"
                    calls = self.sandbox / "whiptail-calls"
                    calls.write_text("")
                    result = self.bash(
                        r'''
args_file="$1" calls="$2" selection="$3"
shift 3
whiptail() {
    local arg screen=''
    for arg in "$@"; do
        case "$arg" in --msgbox|--menu) screen="$arg" ;; esac
    done
    case "$screen" in
        --msgbox|--menu) ;;
        *) blocked unexpected-whiptail-screen "$@" ;;
    esac
    printf '%s\n' "$screen" >> "$calls"
    printf '%s\0' "$@" > "$args_file.$screen"
    if [[ "$screen" == --menu ]]; then printf '%s' "$selection" >&2; fi
}
choose_dnssec "$@"
''',
                        arguments, calls, selection, *dimensions,
                    )
                    self.assert_success(result)
                    self.assertEqual(result.stdout, selection)
                    self.assertEqual(result.stderr, "")
                    self.assertEqual(calls.read_text(), "--msgbox\n--menu\n")
                    calls.unlink()
                    info_args = Path(f"{arguments}.--msgbox").read_bytes().decode().split("\0")[:-1]
                    menu_args = Path(f"{arguments}.--menu").read_bytes().decode().split("\0")[:-1]
                    title = "DNSSEC validation: security vs compatibility"
                    dims = [str(value) for value in (dimensions or (24, 80))]
                    self.assertEqual(info_args[:4], [
                        "--title", title, "--scrolltext", "--msgbox",
                    ])
                    self.assertEqual(info_args[5:], dims)
                    self.assertEqual(menu_args[:9], [
                        "--title", title, "--default-item", "yes", "--menu",
                        "Choose DNSSEC validation mode. DNS-over-TLS remains strict in both modes.",
                        *dims, "2",
                    ])
                    self.assertEqual(menu_args[9:], [
                        "yes", "Strict validation; fail if DNSSEC support is unavailable",
                        "allow-downgrade", "Compatibility fallback; susceptible to downgrade attacks",
                    ])
                    explanation = info_args[4]
                    for text in (
                        "DNSSEC validates signed DNS data",
                        "DNS-over-TLS encrypts the connection",
                        "yes (default): enforce validation",
                        "Invalid signatures are rejected",
                        "Unsigned domains can still resolve",
                        "allow-downgrade: validate when support is detected",
                        "an attacker may be able to trigger this downgrade",
                        "remove DNSSEC protection",
                        "DNS-over-TLS remains strict (yes) with either choice",
                        "Cancel returns without applying changes",
                    ):
                        self.assertIn(text, explanation)
                    self.assertIn("downgrade attacks", menu_args[-1])

    def test_choose_dnssec_propagates_cancellation(self):
        for screen in ("--msgbox", "--menu"):
            for status in (1, 255):
                with self.subTest(screen=screen, status=status):
                    calls = self.sandbox / "cancel-calls"
                    calls.write_text("")
                    result = self.bash(
                        r'''
cancel_screen="$1" cancel_status="$2" calls="$3"
whiptail() {
    local arg screen=''
    for arg in "$@"; do
        case "$arg" in --msgbox|--menu) screen="$arg" ;; esac
    done
    printf '%s\n' "$screen" >> "$calls"
    if [[ "$screen" == "$cancel_screen" ]]; then return "$cancel_status"; fi
    if [[ "$screen" == --menu ]]; then printf yes >&2; fi
}
# A conditional caller suppresses errexit inside choose_dnssec: propagation
# must be explicit, not an accidental consequence of the shell's -e setting.
if choice=$(choose_dnssec); then status=0; else status=$?; fi
printf '%s' "$choice"
exit "$status"
''', screen, status, calls,
                    )
                    self.assertEqual(result.returncode, status, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "")
                    expected = "--msgbox\n" if screen == "--msgbox" else "--msgbox\n--menu\n"
                    self.assertEqual(calls.read_text(), expected)
                    calls.unlink()

    def test_enable_secure_dns_writes_exact_configuration(self):
        servers = "1.1.1.1#cloudflare-dns.com 2606:4700:4700::1111#cloudflare-dns.com"
        for supplied in ((), ("yes",), ("allow-downgrade",)):
            with self.subTest(mode=supplied or "default"):
                body = self.sandbox / "dns.conf"
                calls = self.sandbox / "calls"
                result = self.bash(
                    r'''
body="$1" calls="$2" expected_servers="$3"
shift 3
validate_dns() {
    [[ $# == 1 && "$1" == "$expected_servers" ]]
    printf 'validate\n' >> "$calls"
}
unit_exists() {
    [[ $# == 1 && "$1" == systemd-resolved.service ]]
    printf 'unit\n' >> "$calls"
}
write_config() {
    [[ $# == 1 && "$1" == /etc/systemd/resolved.conf.d/dns_over_tls.conf ]]
    printf 'write\n' >> "$calls"
    cat > "$body"
}
enable_secure_dns "$expected_servers" "$@"
''',
                    body, calls, servers, *supplied,
                )
                self.assert_success(result)
                mode = supplied[0] if supplied else "yes"
                self.assertEqual(body.read_text(), (
                    f"[Resolve]\nDNS={servers}\nFallbackDNS=\nDomains=~.\n"
                    f"DNSOverTLS=yes\nDNSSEC={mode}\nDNSStubListener=yes\n"
                ))
                self.assertEqual(calls.read_text(), "validate\nunit\nwrite\n")
                calls.unlink()

    def test_enable_secure_dns_rejects_invalid_modes_before_dependencies(self):
        for mode in ("no", "YES", "invalid", "yes\nDNSSEC=no", "yes; echo unsafe"):
            with self.subTest(mode=mode):
                result = self.bash(
                    r'''
validate_dns() { blocked validate_dns; }
unit_exists() { blocked unit_exists; }
write_config() { blocked write_config; }
enable_secure_dns '1.1.1.1#cloudflare-dns.com' "$1"
''', mode,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("Unsupported DNSSEC mode:", result.stderr)
                self.assertNotIn("Unexpected external action", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_build_review_includes_selected_dns_details(self):
        for mode in ("yes", "allow-downgrade"):
            with self.subTest(mode=mode):
                result = self.bash(
                    r'''
init_options
for id in "${OPTION_IDS[@]}"; do SELECTED[$id]=off; done
SELECTED[SECURE_DNS]=on
DNS_PROVIDER=Cloudflare
DNS_IPS='1.1.1.1#cloudflare-dns.com'
DNSSEC_MODE="$1"
build_review
''', mode,
                )
                self.assert_success(result)
                self.assertIn("[Network] Strict DNS-over-TLS", result.stdout)
                self.assertIn("DNS provider: Cloudflare\n", result.stdout)
                self.assertIn("DNS servers: 1.1.1.1#cloudflare-dns.com\n", result.stdout)
                self.assertIn(f"DNSSEC mode: {mode}\n", result.stdout)
                self.assertNotIn("[System] Upgrade installed packages", result.stdout)

    def test_configure_dns_action_retries_activation_for_identical_configuration(self):
        result = self.bash(r'''
DNS_IPS='1.1.1.1#cloudflare-dns.com' DNSSEC_MODE=yes
CONFIG_CHANGED=true CONFIG_READY=false
activation_count=0
enable_secure_dns() {
    [[ $# == 2 && "$1" == "$DNS_IPS" && "$2" == "$DNSSEC_MODE" ]]
    CONFIG_CHANGED=false CONFIG_READY=true
}
restart_networking_stack() { activation_count=$((activation_count + 1)); }
configure_dns_action
configure_dns_action
[[ "$activation_count" == 2 && "$CONFIG_CHANGED" == false && "$CONFIG_READY" == true ]]
''')
        self.assert_success(result)
        self.assertEqual(result.stderr, "")

    def test_configure_dns_action_does_not_restart_for_kept_conflict(self):
        result = self.bash(r'''
DNS_IPS='1.1.1.1#cloudflare-dns.com' DNSSEC_MODE=allow-downgrade
CONFIG_POLICY=keep CONFIG_CHANGED=true CONFIG_READY=true
enable_secure_dns() {
    [[ $# == 2 && "$1" == "$DNS_IPS" && "$2" == "$DNSSEC_MODE" ]]
    CONFIG_CHANGED=false CONFIG_READY=false
}
restart_networking_stack() { blocked restart_networking_stack; }
configure_dns_action
[[ "$CONFIG_CHANGED" == false && "$CONFIG_READY" == false ]]
''')
        self.assert_success(result)
        self.assertIn("Conflicting DNS configuration kept; resolver restart skipped.", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_registered_actions_are_functions_and_selection_is_explicit(self):
        result = self.bash(r'''
init_options
[[ ${#OPTION_IDS[@]} -gt 0 ]]
for id in "${OPTION_IDS[@]}"; do
    declare -F "${ACTION[$id]}" >/dev/null
    [[ "${SELECTED[$id]}" == on || "${SELECTED[$id]}" == off ]]
done
selected UPDATE
if selected SECURE_DNS; then exit 1; fi
if selected UNKNOWN_OPTION; then exit 1; fi
SELECTED[SECURE_DNS]=on
selected SECURE_DNS
''')
        self.assert_success(result)

    def test_execute_plan_stops_immediately_when_an_action_fails(self):
        calls = self.sandbox / "execution-calls"
        result = self.bash(
            r'''
calls="$1"
CONFIG_POLICY=keep CONFIG_CHANGED=false BACKUP_DIR=''
EXTRA_PKGS=htop
OPTION_IDS=(FIRST FAIL LATER DISRUPTIVE)
for id in "${OPTION_IDS[@]}"; do
    SELECTED[$id]=on
    LABEL[$id]="$id"
    GROUP[$id]=System
done
GROUP[DISRUPTIVE]=Disruptive
ACTION[FIRST]=first_action
ACTION[FAIL]=failing_action
ACTION[LATER]=later_action
ACTION[DISRUPTIVE]=disruptive_action
report_config_skips() { printf 'skip-check:%s\n' "$1" >> "$calls"; }
first_action() { printf 'first:%s\n' "$1" >> "$calls"; }
failing_action() {
    printf 'fail:%s:%s\n' "$1" "$CURRENT_ACTION" >> "$calls"
    (exit 42)
    printf 'continued-inside-failed-action\n' >> "$calls"
}
later_action() { printf 'later\n' >> "$calls"; }
disruptive_action() { printf 'disruptive\n' >> "$calls"; }
install_selection() { printf 'extras\n' >> "$calls"; }
# Do not put execute_plan in a conditional: that disables Bash errexit.
execute_plan
printf 'continued-after-plan\n' >> "$calls"
''', calls,
        )
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertEqual(calls.read_text(), (
            "skip-check:FIRST\nfirst:FIRST\nskip-check:FAIL\nfail:FAIL:FAIL\n"
        ))
        self.assertNotIn("=> LATER", result.stdout)
        self.assertNotIn("=> DISRUPTIVE", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_main_wizard_cancellation_returns_before_sudo_or_execution(self):
        # main's real EXIT cleanup needs rm; only this test exposes it.
        rm = shutil.which("rm")
        if rm is None:
            self.skipTest("rm is required for main's temporary-directory cleanup")
        (self.bin_dir / "rm").symlink_to(rm)
        for status in (1, 255):
            with self.subTest(status=status):
                calls = self.sandbox / "wizard-calls"
                work_path = self.sandbox / "wizard-work-path"
                result = self.bash(
                    r'''
cancel_status="$1" calls="$2" work_path="$3"
startup_checks() {
    UI_HEIGHT=24 UI_WIDTH=80 LIST_HEIGHT=14
    printf 'startup\n' >> "$calls"
}
ensure_whiptail() {
    [[ -d "$WORK_DIR" && "$WORK_DIR" == "$TMPDIR"/fqs.* ]]
    printf '%s' "$WORK_DIR" > "$work_path"
    printf 'ensure-whiptail\n' >> "$calls"
}
whiptail() {
    [[ "$1" == --title && "$2" == 'FQS - build your plan' ]]
    printf 'wizard\n' >> "$calls"
    return "$cancel_status"
}
execute_plan() { blocked execute_plan; }
main
[[ -z "$SUDO_PID" ]]
printf 'returned\n' >> "$calls"
''', status, calls, work_path,
                )
                self.assert_success(result)
                self.assertEqual(result.stdout, "Cancelled; no selected actions were run.\n")
                self.assertEqual(result.stderr, "")
                self.assertEqual(calls.read_text(), "startup\nensure-whiptail\nwizard\nreturned\n")
                work = Path(work_path.read_text())
                self.assertEqual(work.parent, self.sandbox)
                self.assertFalse(work.exists(), "main's EXIT trap should clean its work directory")
                calls.unlink()
                work_path.unlink()

    def test_valid_packages_accepts_package_names(self):
        for packages in (
            "", "htop", "git curl python3-devel", "libstdc++ gcc-c++",
            "python3.13 foo_bar pkg:arch", "flatpak:org.videolan.VLC",
            "htop flatpak:org.mozilla.firefox",
        ):
            with self.subTest(packages=packages):
                self.assert_success(self.bash('valid_packages "$1"', packages))

    def test_valid_packages_rejects_unsafe_inputs(self):
        for packages in (
            "--assumeyes", "htop -y", "https://example.com/package.rpm",
            "/tmp/package.rpm", "./package.rpm", "htop; id", "htop && id",
            "htop | cat", "$(id)", "`id`", "htop > output", "*.rpm",
            "htop\ncurl", "htop\rcurl", "flatpak:invalid", "flatpak:--system",
        ):
            with self.subTest(packages=packages):
                result = self.bash('valid_packages "$1"', packages)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, "")

    def test_validate_dns_accepts_ipv4_and_ipv6(self):
        for servers in (
            "1.1.1.1", "1.1.1.1#cloudflare-dns.com", "2606:4700:4700::1111",
            "2606:4700:4700::1111#cloudflare-dns.com",
            "1.1.1.1#cloudflare-dns.com 2606:4700:4700::1111#cloudflare-dns.com",
        ):
            with self.subTest(servers=servers):
                result = self.bash('validate_dns "$1"', servers)
                self.assert_success(result)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")

    def test_validate_dns_rejects_invalid_or_injected_values(self):
        for servers in (
            "", "   ", "999.1.1.1", "1.2.3", "2001:db8::gg", "dns.example.com",
            "1.1.1.1\nDNSSEC=no", "1.1.1.1#cloudflare-dns.com\nDNSOverTLS=no",
            "1.1.1.1;id", "$(id)", "fe80::1%eth0", "1.1.1.1#",
            "1.1.1.1#-invalid.example", "1.1.1.1#example.com/unsafe",
        ):
            with self.subTest(servers=servers):
                result = self.bash('validate_dns "$1"', servers)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertTrue(result.stderr.strip())
                self.assertEqual(result.stdout, "")

    def write_configuration(self, target, content, policy="keep", mode="0644", ready="false"):
        work = self.sandbox / "work"
        backup = self.sandbox / "backups"
        work.mkdir(exist_ok=True)
        backup.mkdir(exist_ok=True)
        return self.bash(
            r'''
WORK_DIR="$1" BACKUP_DIR="$2" CONFIG_POLICY="$3"
# Only this helper runs real file commands, with all destinations in the sandbox.
sudo() { command "$@"; }
command_exists() {
    if [[ "$1" == restorecon ]]; then return 1; fi
    command -v "$1" >/dev/null 2>&1
}
CONFIG_CHANGED=true CONFIG_READY="$7"
write_config "$4" "$6" <<< "$5"
printf 'CONFIG_CHANGED=%s\nCONFIG_READY=%s\n' "$CONFIG_CHANGED" "$CONFIG_READY"
''', work, backup, policy, target, content, mode, ready,
        )

    def test_write_config_creates_file_with_requested_permissions(self):
        target = self.sandbox / "new-directory" / "test.conf"
        result = self.write_configuration(target, "new settings", mode="0600")
        self.assert_success(result)
        self.assertEqual(target.read_text(), "new settings\n")
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertIn("CONFIG_CHANGED=true", result.stdout)
        self.assertIn("CONFIG_READY=true", result.stdout)
        self.assertEqual(list((self.sandbox / "backups").iterdir()), [])
        self.assertEqual(list(target.parent.iterdir()), [target])

    def test_write_config_keeps_existing_file_by_default(self):
        target = self.sandbox / "test.conf"
        target.write_text("original\n")
        previous = target.stat()
        result = self.write_configuration(target, "replacement", ready="true")
        self.assert_success(result)
        self.assertEqual(target.read_text(), "original\n")
        self.assertEqual(target.stat().st_ino, previous.st_ino)
        self.assertEqual(target.stat().st_mtime_ns, previous.st_mtime_ns)
        self.assertIn("Keeping existing configuration", result.stdout)
        self.assertIn("CONFIG_CHANGED=false", result.stdout)
        self.assertIn("CONFIG_READY=false", result.stdout)
        self.assertEqual(list((self.sandbox / "backups").iterdir()), [])

    def test_write_config_identical_content_is_noop_even_with_replace(self):
        target = self.sandbox / "test.conf"
        target.write_text("same settings\n")
        target.chmod(0o600)
        previous = target.stat()
        result = self.write_configuration(target, "same settings", policy="replace")
        self.assert_success(result)
        self.assertEqual(target.read_text(), "same settings\n")
        self.assertEqual(target.stat().st_ino, previous.st_ino)
        self.assertEqual(target.stat().st_mtime_ns, previous.st_mtime_ns)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertIn("Already configured:", result.stdout)
        self.assertIn("CONFIG_CHANGED=false", result.stdout)
        self.assertIn("CONFIG_READY=true", result.stdout)
        self.assertEqual(list((self.sandbox / "backups").iterdir()), [])

    def test_write_config_replace_backs_up_original(self):
        target = self.sandbox / "test.conf"
        target.write_text("original\n")
        target.chmod(0o600)
        previous = target.stat()
        result = self.write_configuration(target, "replacement", policy="replace")
        self.assert_success(result)
        self.assertEqual(target.read_text(), "replacement\n")
        self.assertIn("CONFIG_CHANGED=true", result.stdout)
        self.assertIn("CONFIG_READY=true", result.stdout)
        backup = self.sandbox / "backups" / target.relative_to(target.anchor)
        self.assertEqual(backup.read_text(), "original\n")
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(backup.stat().st_mtime_ns, previous.st_mtime_ns)
        self.assertEqual(
            [path for path in (self.sandbox / "backups").rglob("*") if path.is_file()],
            [backup],
        )
        self.assertEqual(list(self.sandbox.glob("test.conf.fqs.*")), [])

    def test_write_config_rejects_existing_and_dangling_symlinks(self):
        for dangling in (False, True):
            for policy in ("keep", "replace"):
                with self.subTest(dangling=dangling, policy=policy):
                    referent = self.sandbox / "referent.conf"
                    if not dangling:
                        referent.write_text("original\n")
                    target = self.sandbox / "link.conf"
                    target.symlink_to(referent)
                    result = self.write_configuration(target, "replacement", policy)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn("Refusing to replace symlink:", result.stderr)
                    self.assertTrue(target.is_symlink())
                    self.assertEqual(os.readlink(target), str(referent))
                    if dangling:
                        self.assertFalse(referent.exists())
                    else:
                        self.assertEqual(referent.read_text(), "original\n")
                        referent.unlink()
                    self.assertEqual(list((self.sandbox / "backups").iterdir()), [])
                    target.unlink()


class ProtonGeTests(unittest.TestCase):
    """Execute only setup_protonge's Python heredoc, never its system actions."""

    TAG = "GE-Proton10-1"
    API_URL = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest"
    ASSET_URL = "https://downloads.example.test/"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fqs-proton-tests-")
        self.addCleanup(self.temp.cleanup)
        self.sandbox = Path(self.temp.name)
        self.destination = self.sandbox / "compatibilitytools.d"
        self.run_count = 0
        source = SCRIPT.read_text()
        marker = "setup_protonge() {\n"
        self.assertIn(marker, source)
        body = re.search(r"<<'PY'\n(.*?)\nPY\n", source.split(marker, 1)[1], re.DOTALL)
        if body is None:
            self.fail("setup_protonge must contain its Python heredoc")
        self.code = compile(body.group(1), f"{SCRIPT}:setup_protonge", "exec")

    def archive(self, root=None, member_name=None, symlink=None):
        root = root or f"{self.TAG}-x86_64"
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as package:
            directory = tarfile.TarInfo(root)
            directory.type = tarfile.DIRTYPE
            package.addfile(directory)
            member = tarfile.TarInfo(member_name or f"{root}/proton")
            if symlink is not None:
                member.type = tarfile.SYMTYPE
                member.linkname = symlink
                package.addfile(member)
            else:
                content = b"offline Proton fixture\n"
                member.size = len(content)
                package.addfile(member, io.BytesIO(content))
        return buffer.getvalue()

    def run_proton(self, archive, checksum=None, legacy=False):
        self.run_count += 1
        self.work = self.sandbox / f"work-{self.run_count}"
        self.work.mkdir()
        self.archive_name = f"{self.TAG}{'' if legacy else '-x86_64'}.tar.gz"
        self.checksum_name = self.archive_name.removesuffix(".tar.gz") + ".sha512sum"
        arm_name = f"{self.TAG}-aarch64.tar.gz"
        # Put the wrong architecture first to catch first-archive selection bugs.
        names = [arm_name, arm_name.removesuffix(".tar.gz") + ".sha512sum",
                 self.archive_name, self.checksum_name]
        release = {
            "tag_name": self.TAG,
            "assets": [{"name": name, "browser_download_url": self.ASSET_URL + name}
                       for name in names],
        }
        digest = checksum if checksum is not None else hashlib.sha512(archive).hexdigest()
        responses = {
            self.API_URL: json.dumps(release).encode(),
            self.ASSET_URL + self.checksum_name: f"{digest}  {self.archive_name}\n".encode(),
            self.ASSET_URL + self.archive_name: archive,
        }
        self.requests = []
        self.output = io.StringIO()

        def urlopen(url, timeout):
            self.assertEqual(timeout, 60)
            self.requests.append(url)
            self.assertIn(url, responses, "Unexpected download (no network is permitted)")
            return io.BytesIO(responses[url])

        with (
            mock.patch("urllib.request.urlopen", side_effect=urlopen),
            mock.patch("platform.machine", return_value="x86_64"),
            mock.patch.object(sys, "argv", ["proton-test", str(self.work), str(self.destination)]),
            redirect_stdout(self.output),
        ):
            exec(self.code, {"__name__": "__main__"})  # noqa: S102 - checked-in code, mocked I/O

    def test_selects_x86_64_asset_and_matching_checksum_and_extracts_data(self):
        self.run_proton(self.archive())
        target = self.destination / f"{self.TAG}-x86_64"
        self.assertEqual((target / "proton").read_bytes(), b"offline Proton fixture\n")
        self.assertEqual(self.requests, [
            self.API_URL, self.ASSET_URL + self.checksum_name,
            self.ASSET_URL + self.archive_name,
        ])
        self.assertEqual(list(self.destination.iterdir()), [target])
        self.assertIn(f"Installed {target.name}.", self.output.getvalue())

    def test_accepts_legacy_x86_64_asset_and_tag_root(self):
        self.run_proton(self.archive(root=self.TAG), legacy=True)
        self.assertTrue((self.destination / self.TAG / "proton").is_file())
        self.assertEqual(self.requests[-2:], [
            self.ASSET_URL + f"{self.TAG}.sha512sum",
            self.ASSET_URL + f"{self.TAG}.tar.gz",
        ])

    def test_rejects_sha512_mismatch_before_extraction(self):
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.run_proton(self.archive(), checksum="0" * 128)
        self.assertFalse((self.work / "proton").exists())
        self.assertFalse(self.destination.exists())

    def test_rejects_traversal_and_absolute_paths(self):
        for member in ("../escaped", f"{self.TAG}-x86_64/../../escaped",
                       str(self.sandbox / "escaped")):
            with self.subTest(member=member):
                with self.assertRaisesRegex(ValueError, "Unexpected archive path"):
                    self.run_proton(self.archive(member_name=member))
                self.assertFalse((self.sandbox / "escaped").exists())
                self.assertFalse(self.destination.exists())
                self.assertEqual(list((self.work / "proton").iterdir()), [])

    def test_rejects_unexpected_or_multiple_archive_roots(self):
        for root, member in (("unrelated", "unrelated/proton"),
                             (self.TAG, "another-root/proton")):
            with self.subTest(root=root, member=member):
                with self.assertRaisesRegex(ValueError, "Unexpected archive root directory"):
                    self.run_proton(self.archive(root=root, member_name=member))
                self.assertFalse(self.destination.exists())
                self.assertEqual(list((self.work / "proton").iterdir()), [])

    def test_data_filter_rejects_symlink_escaping_staging(self):
        with self.assertRaises(tarfile.FilterError):
            self.run_proton(self.archive(symlink="../../escaped"))
        self.assertFalse((self.sandbox / "escaped").exists())
        self.assertFalse(self.destination.exists())
        self.assertFalse((self.work / "proton" / f"{self.TAG}-x86_64" / "proton").is_symlink())

    def test_keeps_existing_install_for_both_accepted_root_names(self):
        for root in (self.TAG, f"{self.TAG}-x86_64"):
            with self.subTest(root=root):
                target = self.destination / root
                target.mkdir(parents=True)
                installed = target / "proton"
                installed.write_bytes(b"existing local installation\n")
                previous = installed.stat()
                with self.assertRaises(SystemExit) as stopped:
                    self.run_proton(self.archive(root=root))
                self.assertEqual(stopped.exception.code, 0)
                self.assertEqual(installed.read_bytes(), b"existing local installation\n")
                self.assertEqual(installed.stat().st_ino, previous.st_ino)
                self.assertEqual(installed.stat().st_mtime_ns, previous.st_mtime_ns)
                self.assertEqual(list(target.iterdir()), [installed])
                self.assertIn("Keeping existing Proton-GE installation:", self.output.getvalue())
                if root == self.TAG:
                    self.assertEqual(self.requests, [self.API_URL])
                self.assertFalse((self.work / "proton" / root).exists())
                shutil.rmtree(target)


if __name__ == "__main__":
    unittest.main()

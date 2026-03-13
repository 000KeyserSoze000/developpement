#!/usr/bin/env python3
"""
IONOS PLESK Server Dashboard - Version optimisée
Application TUI pour la gestion de serveur IONOS PLESK
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import paramiko
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, Footer, Header, Input, Log, Static

if TYPE_CHECKING:
    pass

# ==============================================================================
# Configuration Constants
# ==============================================================================

DOMAINS: list[str] = [
    "cafedantan.fr",
    "dj-thoons.fr",
    "equigenio.fr",
    "hnwi.fr",
    "etsdelon.fr",
    "botmonster.fr",
]

LOG_TYPES: list[tuple[str, str]] = [
    ("Apache", "access_log"),
    ("Sys", "error_log"),
    ("Proxy", "proxy_error_log"),
    ("SSL", "access_ssl_log"),
]

SERVER_IP: str = "212.227.84.152"

# Paths
LOG_DIR: Path = Path.home() / ".ionos_dashboard"
LOG_DIR.mkdir(exist_ok=True)
CONFIG_FILE: Path = LOG_DIR / "config.json"
HISTORY_FILE: Path = LOG_DIR / "command_history.json"

# Domain information for display
DOMAIN_INFO: dict[str, dict[str, Any]] = {
    "cafedantan.fr": {
        "ip": "212.227.84.152",
        "ssl_days": 145,
        "services": ["FTP", "IMAP", "Plesk", "POP3", "Web"],
        "spf": "v=spf1 a mx a:vps.cafedantan.fr ip4:212.227.84.152 -all",
        "dkim": "v=DKIM1; t=s; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
        "dmarc": "v=DMARC1; p=reject; adkim=r; aspf=r",
    },
    "dj-thoons.fr": {
        "ip": "212.227.84.152",
        "ssl_days": 156,
        "services": ["FTP", "IMAP", "Plesk", "POP3", "Web"],
        "spf": "v=spf1 a mx a:vps.dj-thoons.fr ip4:212.227.84.152 -all",
        "dkim": "v=DKIM1; t=s; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
        "dmarc": "v=DMARC1; p=reject; adkim=r; aspf=r",
    },
    "equigenio.fr": {
        "ip": "212.227.84.152",
        "ssl_days": 89,
        "services": ["FTP", "IMAP", "Plesk", "POP3", "Web"],
        "spf": "v=spf1 a mx a:vps.equigenio.fr ip4:212.227.84.152 -all",
        "dkim": "v=DKIM1; t=s; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
        "dmarc": "v=DMARC1; p=reject; adkim=r; aspf=r",
    },
    "hnwi.fr": {
        "ip": "212.227.84.152",
        "ssl_days": 86,
        "services": ["FTP", "IMAP", "Plesk", "POP3", "Web"],
        "spf": "v=spf1 a mx a:vps.hnwi.fr ip4:212.227.84.152 -all",
        "dkim": "v=DKIM1; t=s; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
        "dmarc": "v=DMARC1; p=reject; adkim=r; aspf=r",
    },
    "etsdelon.fr": {
        "ip": "212.227.84.152",
        "ssl_days": 124,
        "services": ["FTP", "IMAP", "Plesk", "POP3", "Web"],
        "spf": "v=spf1 a mx a:vps.etsdelon.fr ip4:212.227.84.152 -all",
        "dkim": "v=DKIM1; t=s; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
        "dmarc": "v=DMARC1; p=reject; adkim=r; aspf=r",
    },
    "botmonster.fr": {
        "ip": "212.227.84.152",
        "ssl_days": 98,
        "services": ["FTP", "IMAP", "Plesk", "POP3", "Web"],
        "spf": "v=spf1 a mx a:vps.botmonster.fr ip4:212.227.84.152 -all",
        "dkim": "v=DKIM1; t=s; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
        "dmarc": "v=DMARC1; p=reject; adkim=r; aspf=r",
    },
}

# SSH Command templates
SSH_COMMANDS: dict[str, list[str]] = {
    "monitor": ["top -bn1 | head -n 12", "df -h /"],
    "update": ["apt-get update && apt-get upgrade -y"],
    "plesk_up": ["plesk installer update --select-release-current"],
    "restart_web": ["systemctl reload php*-fpm", "systemctl restart nginx"],
    "view_logs": ["tail -n 50 /var/www/vhosts/{domain}/logs/{log}"],
    "purge_log": ["truncate -s 0 /var/www/vhosts/{domain}/logs/{log}", "echo 'Log purged.'"],
    "global_health": [
        "plesk bin site --info {domain} | grep 'PHP version'",
        "plesk bin certificate --details -domain {domain} | grep -E 'expires|status'",
        "plesk bin subscription --info {domain} | grep -A 2 'Disk usage'",
    ],
    "backup_sql": [
        "plesk db dump $(plesk db -e 'show databases' | grep {domain} | head -n 1) > /root/tmp_db.sql",
        "echo 'Dump saved to /root/tmp_db.sql'",
    ],
}


# ==============================================================================
# Helper Functions
# ==============================================================================

def load_config() -> dict[str, Any]:
    """Load configuration from JSON file."""
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to JSON file."""
    try:
        config["timestamp"] = datetime.now().isoformat()
        with CONFIG_FILE.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except OSError:
        pass


def load_history() -> list[dict[str, str]]:
    """Load command history from JSON file."""
    if HISTORY_FILE.exists():
        try:
            with HISTORY_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_history(history: list[dict[str, str]]) -> None:
    """Save command history to JSON file (keep last 100 entries)."""
    try:
        with HISTORY_FILE.open("w", encoding="utf-8") as f:
            json.dump(history[-100:], f, indent=2)
    except OSError:
        pass


# ==============================================================================
# Main Application
# ==============================================================================

class IonosDashboard(App):
    """
    Application TUI pour la gestion de serveur IONOS PLESK.
    
    Fonctionnalités:
    - Sélection de domaine avec actions contextuelles
    - Visualisation et gestion des logs
    - Exécution de commandes SSH
    - Historique des commandes
    """

    TITLE = "IONOS PLESK CONTROL CENTER"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear_logs", "Clear"),
        Binding("ctrl+s", "save_output", "Save"),
        Binding("ctrl+d", "show_domain_info", "Info"),
    ]

    CSS = """
    $bg:      #0D0D0D;
    $surface: #1A1A1A;
    $border:  #2A2A2A;
    $accent:  #00FF88;
    $warn:    #FFB800;
    $danger:  #FF3B3B;
    $muted:   #3A3A3A;
    $text:    #CCCCCC;
    $dim:     #666666;
    $sel:     #1A3A2A;

    Screen { 
        background: $bg; 
        color: $text; 
    }

    Header { 
        background: $surface; 
        color: $accent; 
        border-bottom: solid $border; 
        text-style: bold; 
    }

    Footer { 
        background: $surface; 
        color: $dim;    
        border-top: solid $border; 
    }

    #auth_bar {
        height: 3; 
        background: $surface; 
        border-bottom: solid $border;
        padding: 0 2; 
    }

    #lbl_auth  { 
        color: $dim; 
        width: auto; 
        margin-right: 2; 
        text-style: bold;
    }

    #pwd_input { 
        width: 30; 
        background: $bg; 
        color: $accent; 
        border: solid $muted;
    }

    #pwd_input:focus { 
        border: solid $accent; 
        background: #1a2a1a;
    }

    #server_bar {
        height: auto; 
        background: $surface; 
        border-bottom: solid $border;
        padding: 1 2;
    }

    #server_info {
        height: auto;
        layout: horizontal;
    }

    #lbl_srv_label { 
        color: $dim; 
        text-style: bold; 
        width: auto; 
        margin-right: 2; 
    }

    #lbl_srv_ip    { 
        color: $accent; 
        text-style: bold; 
        width: auto;
    }

    #server_buttons {
        height: auto;
        layout: horizontal;
        width: 1fr;
        margin-top: 1;
    }

    #main_layout { 
        height: 1fr; 
        layout: horizontal;
    }

    #sidebar {
        width: 30; 
        background: $surface; 
        border-right: solid $border;
        padding: 1 1;
    }

    .sec { 
        color: $accent; 
        text-style: bold; 
        margin-top: 1; 
        margin-bottom: 1; 
        padding: 0 1;
    }

    Button {
        margin: 0 0 1 0;
        padding: 0 1;
        width: 1fr;
    }

    .btn-sm {
        background: $bg; 
        color: $accent; 
        border: solid $muted;
    }

    .btn-sm:hover { 
        background: $muted; 
        border: solid $accent; 
    }

    .btn-domain {
        background: $bg; 
        color: $text; 
        border: solid $muted;
    }

    .btn-domain:hover { 
        background: $muted; 
        border: solid $accent; 
        color: $accent; 
    }

    .btn-domain-active {
        background: $sel; 
        color: $accent; 
        border: solid $accent;
    }

    .btn-sub {
        background: $bg; 
        color: $accent; 
        border: solid $muted;
    }

    .btn-sub:hover { 
        background: $muted; 
        border: solid $accent; 
    }

    .btn-log {
        background: $bg; 
        color: $warn; 
        border: solid $muted;
    }

    .btn-log:hover { 
        background: $muted; 
        border: solid $warn; 
    }

    .btn-log-active {
        background: #2E2000; 
        color: $warn; 
        border: solid $warn;
    }

    .btn-log-action {
        background: $bg; 
        color: $warn; 
        border: solid $muted;
    }

    .btn-log-action:hover { 
        background: $muted; 
        border: solid $warn; 
    }

    .btn-danger {
        background: $bg; 
        color: $danger; 
        border: solid $muted;
    }

    .btn-danger:hover { 
        background: $muted; 
        border: solid $danger; 
    }

    .btn-util {
        margin-top: 2;
        background: $bg; 
        color: $dim; 
        border: solid $border;
    }

    .btn-util:hover { 
        color: $text; 
        border: solid $muted; 
    }

    .btn-info {
        margin-top: 1;
        background: $bg; 
        color: $accent; 
        border: solid $muted;
    }

    .btn-info:hover { 
        background: $muted; 
        border: solid $accent; 
    }

    .running { 
        color: $warn   !important; 
        border: solid $warn   !important; 
    }

    .success { 
        color: $accent !important; 
        border: solid $accent !important;
    }

    .error   { 
        color: $danger !important; 
        border: solid $danger !important;
    }

    #log_area { 
        height: 1fr; 
        background: $bg; 
        layout: vertical;
        width: 1fr;
    }

    #log_header { 
        height: 1; 
        color: $dim; 
        padding: 0 2; 
        background: $surface; 
        border-bottom: solid $border;
    }

    #log_status {
        height: 1;
        color: $dim;
        padding: 0 2;
        background: $surface;
        border-bottom: solid $border;
    }

    Log { 
        background: $bg; 
        color: $accent; 
        height: 1fr; 
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.root_password: str = ""
        self.selected_domain: str | None = None
        self.selected_log_type: str | None = None
        self.ssh_connected: bool = False
        self.command_count: int = 0
        self.command_history: list[dict[str, str]] = load_history()
        
        # Load saved configuration
        config = load_config()
        self.selected_domain = config.get("domain")
        self.selected_log_type = config.get("log_type")

    # ==========================================================================
    # Compose Methods
    # ==========================================================================

    def compose(self) -> ComposeResult:
        """Compose the main application layout."""
        yield Header()

        with Horizontal(id="auth_bar"):
            yield Static("ROOT PASSWORD", id="lbl_auth")
            yield Input(placeholder="enter password…", password=True, id="pwd_input")

        with Vertical(id="server_bar"):
            with Horizontal(id="server_info"):
                yield Static("SERVER", id="lbl_srv_label")
                yield Static(SERVER_IP, id="lbl_srv_ip")
            with Horizontal(id="server_buttons"):
                yield Button("MONITOR", id="monitor", classes="btn-sm")
                yield Button("UPDATE", id="update", classes="btn-sm")
                yield Button("PLESK UP", id="plesk_up", classes="btn-sm")
                yield Button("RELOAD WEB", id="restart_web", classes="btn-sm")

        with Horizontal(id="main_layout"):
            with ScrollableContainer(id="sidebar"):
                yield from self._compose_sidebar()

            with Vertical(id="log_area"):
                yield Static(" OUTPUT", id="log_header")
                yield Static(f"Commands: 0", id="log_status")
                yield Log()

        yield Footer()

    def _compose_sidebar(self) -> ComposeResult:
        """Compose sidebar content using yield from pattern."""
        # Domains section
        yield Static("DOMAINES", classes="sec")
        for domain in DOMAINS:
            is_active = domain == self.selected_domain
            btn_class = "btn-domain-active" if is_active else "btn-domain"
            prefix = "◆ " if is_active else "  "
            yield Button(f"{prefix}{domain}", id=f"dom_{domain}", classes=btn_class)

        # Domain actions (shown when domain selected)
        if self.selected_domain:
            yield Button("  HEALTH CHECK", id="global_health", classes="btn-sub")
            yield Button("  BACKUP SQL", id="backup_sql", classes="btn-sub")

        # Logs section
        yield Static("LOGS", classes="sec")
        for label, key in LOG_TYPES:
            is_active = key == self.selected_log_type
            btn_class = "btn-log-active" if is_active else "btn-log"
            prefix = "▶ " if is_active else "  "
            yield Button(f"{prefix}{label}", id=f"log_{key}", classes=btn_class)

        # Log actions (shown when log type selected)
        if self.selected_log_type:
            yield Button("  VIEW", id="view_logs", classes="btn-log-action")
            yield Button("  DOWNLOAD", id="download_log", classes="btn-log-action")
            yield Button("  PURGE", id="purge_log", classes="btn-danger")

        # Utilities section
        yield Static("UTILITAIRES", classes="sec")
        yield Button("INFOS DOMAINE", id="btn_info", classes="btn-info")
        yield Button("CLEAR CONSOLE", id="btn_clear", classes="btn-util")
        yield Button("SAVE OUTPUT", id="btn_save", classes="btn-util")

    def _refresh_sidebar(self) -> None:
        """Refresh sidebar with current state."""
        sidebar = self.query_one("#sidebar", ScrollableContainer)
        sidebar.remove_children()

        # Build new content
        content = list(self._compose_sidebar())
        for widget in content:
            sidebar.mount(widget)

    def _update_status_bar(self) -> None:
        """Update status bar with current information."""
        try:
            status_widget = self.query_one("#log_status", Static)
            domain = self.selected_domain or "None"
            log = self.selected_log_type or "None"
            status_text = f"Commands: {self.command_count} | Domain: {domain} | Log: {log}"
            status_widget.update(status_text)
        except Exception:
            pass

    # ==========================================================================
    # Event Handlers
    # ==========================================================================

    def on_mount(self) -> None:
        """Handle application mount event."""
        self._update_status_bar()
        if self.selected_domain or self.selected_log_type:
            self._refresh_sidebar()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input value changes."""
        if event.input.id == "pwd_input":
            self.root_password = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id or ""

        # Domain selection
        if button_id.startswith("dom_"):
            domain = button_id[4:]
            self.selected_domain = domain
            save_config({
                "domain": self.selected_domain,
                "log_type": self.selected_log_type,
            })
            self._refresh_sidebar()
            self._update_status_bar()
            self._log_command(f"select_domain:{domain}", "selected")
            return

        # Log type selection
        if button_id.startswith("log_"):
            key = button_id[4:]
            self.selected_log_type = key
            save_config({
                "domain": self.selected_domain,
                "log_type": self.selected_log_type,
            })
            self._refresh_sidebar()
            self._update_status_bar()
            self._log_command(f"select_log:{key}", "selected")
            return

        # Clear console
        if button_id == "btn_clear":
            self.action_clear_logs()
            return

        # Show domain info
        if button_id == "btn_info":
            self.action_show_domain_info()
            return

        # Save output
        if button_id == "btn_save":
            self.action_save_output()
            return

        # Download log
        if button_id == "download_log":
            self.run_ssh(event.button, [], is_download=True)
            return

        # Other actions from SSH_COMMANDS
        if button_id in SSH_COMMANDS:
            self.run_ssh(event.button, SSH_COMMANDS[button_id])

    # ==========================================================================
    # Actions
    # ==========================================================================

    def action_clear_logs(self) -> None:
        """Clear console logs."""
        log_widget = self.query_one(Log)
        log_widget.clear()
        self.command_count = 0
        self._update_status_bar()
        self._log_command("clear_console", "success")

    def action_save_output(self) -> None:
        """Save output to file."""
        log_widget = self.query_one(Log)
        output = log_widget.export_text()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = LOG_DIR / f"output_{timestamp}.log"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(output)
            log_widget.write_line(f"\n  ✓ Output saved to {filename}")
            self._log_command("save_output", f"saved:{filename}")
        except Exception as e:
            log_widget.write_line(f"\n  [ERROR] Could not save: {e}")

    def action_show_domain_info(self) -> None:
        """Show domain info."""
        log_widget = self.query_one(Log)
        if self.selected_domain:
            info = self.format_domain_info(self.selected_domain)
            log_widget.write_line(info)
            self._log_command(f"show_info:{self.selected_domain}", "displayed")
        else:
            log_widget.write_line("  [!] Sélectionnez d'abord un domaine")

    # ==========================================================================
    # SSH Operations
    # ==========================================================================

    @work(exclusive=True, thread=True)
    def run_ssh(
        self, 
        button_widget: Button, 
        commands: list[str], 
        is_download: bool = False
    ) -> None:
        """Execute SSH commands or download files."""
        log_widget = self.query_one(Log)

        if not self.root_password:
            log_widget.write_line("  [!] Root password required.")
            return

        button_widget.remove_class("success", "error")
        button_widget.add_class("running")

        client: paramiko.SSHClient | None = None
        command_status = "success"

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                SERVER_IP, 
                username="root", 
                password=self.root_password, 
                timeout=10
            )

            self.ssh_connected = True
            domain = self.selected_domain or ""
            log_type = self.selected_log_type or ""

            if is_download:
                remote = f"/var/www/vhosts/{domain}/logs/{log_type}"
                local = os.path.join(LOG_DIR, f"{domain}_{log_type}.txt")
                log_widget.write_line(f"  ↓ Downloading {log_type} …")
                try:
                    sftp = client.open_sftp()
                    sftp.get(remote, local)
                    sftp.close()
                    log_widget.write_line(f"  ✓ Saved → {local}")
                    self._log_command(f"download:{log_type}", f"saved:{local}")
                except Exception as e:
                    log_widget.write_line(f"  [ERROR] Download failed: {e}")
                    command_status = "failed"
            else:
                for cmd in commands:
                    cmd = cmd.replace("{domain}", domain).replace("{log}", log_type)
                    log_widget.write_line(f"\n  $ {cmd}")
                    
                    _, stdout, stderr = client.exec_command(cmd)
                    out = stdout.read().decode().strip()
                    err = stderr.read().decode().strip()
                    
                    if out:
                        log_widget.write_line(out)
                    if err:
                        log_widget.write_line(f"  [!] {err}")

            button_widget.remove_class("running")
            button_widget.add_class("success")
            log_widget.write_line("  ✓ Done.")

            self.command_count += 1
            self._update_status_bar()
            self._log_command(commands[0] if commands else "download", command_status)

        except paramiko.AuthenticationException:
            log_widget.write_line("\n  [ERROR] Authentication failed - invalid password")
            button_widget.remove_class("running")
            button_widget.add_class("error")
            self.ssh_connected = False
            self._log_command("ssh_connect", "auth_failed")

        except Exception as exc:
            log_widget.write_line(f"\n  [ERROR] {type(exc).__name__}: {exc}")
            button_widget.remove_class("running")
            button_widget.add_class("error")
            self.ssh_connected = False
            self._log_command("ssh_connect", f"error:{type(exc).__name__}")

        finally:
            if client:
                client.close()
            log_widget.scroll_end()

    # ==========================================================================
    # Display Methods
    # ==========================================================================

    def format_domain_info(self, domain: str) -> str:
        """Format domain info for display."""
        info = DOMAIN_INFO.get(domain)
        if not info:
            return f"No info for {domain}"

        ssl_days = info["ssl_days"]
        if ssl_days > 30:
            ssl_icon = "🟢"
        elif ssl_days > 7:
            ssl_icon = "🟡"
        else:
            ssl_icon = "🔴"

        services_status = " ".join([f"{srv}:✅" for srv in info["services"]])

        lines = [
            "",
            "=" * 60,
            f"  INFOS DOMAINE: {domain.upper()}",
            "=" * 60,
            "",
            f"  [IP/A]  ✅ {info['ip']}",
            f"  [SSL]   {ssl_icon} {ssl_days} jours",
            f"  [SRV]   {services_status}",
            "",
            "  [DÉTAILS DES ENREGISTREMENTS DNS]",
            "  " + "─" * 56,
            f"    SPF   : {info['spf']}",
            f"    DKIM  : {info['dkim']}",
            f"    DMARC : {info['dmarc']}",
            "",
            "=" * 60,
        ]

        return "\n".join(lines)

    # ==========================================================================
    # History Management
    # ==========================================================================

    def _log_command(self, command: str, status: str) -> None:
        """Log command to history file."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "domain": self.selected_domain or "",
            "command": command,
            "status": status,
        }
        self.command_history.append(entry)
        save_history(self.command_history)

    def on_unmount(self) -> None:
        """Handle application unmount event."""
        # Ensure history is saved
        if self.command_history:
            save_history(self.command_history)


# ==============================================================================
# Entry Point
# ==============================================================================

def main() -> None:
    """Main entry point for the application."""
    app = IonosDashboard()
    app.run()


if __name__ == "__main__":
    main()

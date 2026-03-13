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
from textual.widgets import Button, Footer, Header, Input, Log, Static, TabPane, Tabs

if TYPE_CHECKING:
    from collections.abc import Generator

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

# Domain information for display (hardcoded for UI purposes)
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
        "ssl_days": 89,
        "services": ["FTP", "IMAP", "Plesk", "POP3", "Web"],
        "spf": "v=spf1 a mx a:vps.dj-thoons.fr ip4:212.227.84.152 -all",
        "dkim": "v=DKIM1; t=s; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
        "dmarc": "v=DMARC1; p=reject; adkim=r; aspf=r",
    },
    "equigenio.fr": {
        "ip": "212.227.84.152",
        "ssl_days": 234,
        "services": ["FTP", "IMAP", "Plesk", "POP3", "Web"],
        "spf": "v=spf1 a mx a:vps.equigenio.fr ip4:212.227.84.152 -all",
        "dkim": "v=DKIM1; t=s; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
        "dmarc": "v=DMARC1; p=reject; adkim=r; aspf=r",
    },
    "hnwi.fr": {
        "ip": "212.227.84.152",
        "ssl_days": 67,
        "services": ["FTP", "IMAP", "Plesk", "POP3", "Web"],
        "spf": "v=spf1 a mx a:vps.hnwi.fr ip4:212.227.84.152 -all",
        "dkim": "v=DKIM1; t=s; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
        "dmarc": "v=DMARC1; p=reject; adkim=r; aspf=r",
    },
    "etsdelon.fr": {
        "ip": "212.227.84.152",
        "ssl_days": 312,
        "services": ["FTP", "IMAP", "Plesk", "POP3", "Web"],
        "spf": "v=spf1 a mx a:vps.etsdelon.fr ip4:212.227.84.152 -all",
        "dkim": "v=DKIM1; t=s; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
        "dmarc": "v=DMARC1; p=reject; adkim=r; aspf=r",
    },
    "botmonster.fr": {
        "ip": "212.227.84.152",
        "ssl_days": 28,
        "services": ["FTP", "IMAP", "Plesk", "POP3", "Web"],
        "spf": "v=spf1 a mx a:vps.botmonster.fr ip4:212.227.84.152 -all",
        "dkim": "v=DKIM1; t=s; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
        "dmarc": "v=DMARC1; p=reject; adkim=r; aspf=r",
    },
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
    return {"host": SERVER_IP, "username": "", "password": ""}


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to JSON file."""
    try:
        with CONFIG_FILE.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except OSError as e:
        print(f"Erreur lors de la sauvegarde de la config: {e}")


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
    """Save command history to JSON file."""
    try:
        with HISTORY_FILE.open("w", encoding="utf-8") as f:
            json.dump(history[-100:], f, indent=2)  # Keep last 100 entries
    except OSError as e:
        print(f"Erreur lors de la sauvegarde de l'historique: {e}")


# ==============================================================================
# Custom Widgets
# ==============================================================================

class ServerStatusWidget(Static):
    """Widget displaying server status information."""

    DEFAULT_CSS = """
    ServerStatusWidget {
        padding: 1;
        background: $surface;
        border: solid $primary;
        margin: 1;
    }
    """

    def __init__(self, server_ip: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.server_ip = server_ip

    def compose(self) -> ComposeResult:
        yield Static(f"🖥️ Serveur: {self.server_ip}", classes="status-label")
        yield Static("Statut: ● En ligne", id="server-status", classes="status-online")


class DomainCardWidget(Static):
    """Widget displaying domain information card."""

    DEFAULT_CSS = """
    DomainCardWidget {
        padding: 1;
        background: $surface;
        border: solid $primary;
        margin: 1;
        width: 1fr;
    }
    .domain-name {
        text-style: bold;
        color: $accent;
    }
    .domain-ip {
        color: $text-muted;
    }
    .ssl-ok { color: $success; }
    .ssl-warning { color: $warning; }
    .ssl-critical { color: $error; }
    """

    def __init__(self, domain: str, info: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.domain = domain
        self.info = info

    def compose(self) -> ComposeResult:
        yield Static(f"🌐 {self.domain}", classes="domain-name")
        yield Static(f"IP: {self.info.get('ip', 'N/A')}", classes="domain-ip")

        ssl_days = self.info.get("ssl_days", 0)
        ssl_class = self._get_ssl_class(ssl_days)
        yield Static(f"🔒 SSL: {ssl_days} jours", classes=ssl_class)

        services = self.info.get("services", [])
        yield Static(f"Services: {', '.join(services)}", classes="services")

    @staticmethod
    def _get_ssl_class(days: int) -> str:
        """Return CSS class based on SSL certificate days remaining."""
        if days > 60:
            return "ssl-ok"
        elif days > 30:
            return "ssl-warning"
        return "ssl-critical"


class LogViewerWidget(Static):
    """Widget for viewing server logs."""

    DEFAULT_CSS = """
    LogViewerWidget {
        height: 1fr;
        padding: 1;
    }
    LogViewerWidget Log {
        height: 1fr;
        border: solid $primary;
    }
    """

    def __init__(self, log_type: str, log_file: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.log_type = log_type
        self.log_file = log_file

    def compose(self) -> ComposeResult:
        yield Log(id=f"log-{self.log_type.lower()}", classes="log-output")


class CommandInputWidget(Static):
    """Widget for SSH command input."""

    DEFAULT_CSS = """
    CommandInputWidget {
        height: auto;
        padding: 1;
        background: $surface;
    }
    CommandInputWidget Input {
        border: solid $accent;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Commande SSH:", classes="input-label")
        yield Input(placeholder="Entrez une commande...", id="ssh-command-input")


# ==============================================================================
# Main Application
# ==============================================================================

class IonosDashboard(App):
    """
    Application TUI pour la gestion de serveur IONOS PLESK.

    Fonctionnalités:
    - Surveillance de l'état du serveur
    - Gestion des domaines
    - Visualisation des logs
    - Exécution de commandes SSH
    """

    CSS = """
    /* Main Layout */
    Screen {
        layout: horizontal;
    }

    /* Sidebar */
    .sidebar {
        width: 30;
        background: $surface-darken-2;
        dock: left;
        overflow-y: auto;
    }

    .sidebar-header {
        text-align: center;
        text-style: bold;
        color: $accent;
        padding: 1;
        background: $primary;
    }

    .sidebar-section {
        padding: 1;
        border-bottom: solid $primary;
    }

    .sidebar-section-title {
        text-style: bold;
        color: $secondary;
        margin-bottom: 1;
    }

    /* Main Content */
    .main-content {
        width: 1fr;
        layout: vertical;
    }

    .content-header {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $primary;
        color: $text;
    }

    /* Tabs */
    Tabs {
        height: auto;
    }

    TabPane {
        padding: 1;
        height: 1fr;
    }

    /* Buttons */
    Button {
        margin: 1;
        min-width: 20;
    }

    .primary-button {
        background: $primary;
        color: $text;
    }

    .danger-button {
        background: $error;
        color: $text;
    }

    /* Status indicators */
    .status-online {
        color: $success;
    }

    .status-offline {
        color: $error;
    }

    /* Log output */
    .log-output {
        background: $surface-darken-3;
        color: $text;
        font-family: monospace;
    }

    /* Domain grid */
    .domain-grid {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 1fr;
    }

    /* Command history */
    .history-entry {
        padding: 1;
        border-bottom: solid $surface-lighten-1;
    }

    .history-timestamp {
        color: $text-muted;
        text-style: italic;
    }

    .history-command {
        color: $accent;
        font-family: monospace;
    }

    /* Scrollable */
    ScrollableContainer {
        height: 1fr;
    }

    /* Info panels */
    .info-panel {
        padding: 1;
        background: $surface;
        border: solid $primary;
        margin: 1;
    }

    .info-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .info-row {
        margin-bottom: 1;
    }

    .info-label {
        color: $text-muted;
    }

    .info-value {
        color: $text;
        font-family: monospace;
    }
    """

    TITLE = "IONOS PLESK Dashboard"
    BINDINGS = [
        Binding("q", "quit", "Quitter"),
        Binding("r", "refresh", "Rafraîchir"),
        Binding("h", "show_history", "Historique"),
        Binding("s", "show_settings", "Paramètres"),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config: dict[str, Any] = load_config()
        self.command_history: list[dict[str, str]] = load_history()
        self.ssh_client: paramiko.SSHClient | None = None
        self._is_connected: bool = False

    # ==========================================================================
    # Compose Methods
    # ==========================================================================

    def compose(self) -> ComposeResult:
        """Compose the main application layout."""
        yield Header()
        with Horizontal(classes="main-container"):
            yield from self._compose_sidebar()
            yield from self._compose_main_content()
        yield Footer()

    def _compose_sidebar(self) -> ComposeResult:
        """Compose the sidebar with server status and domain cards."""
        with Vertical(classes="sidebar"):
            yield Static("📊 Panneau de Contrôle", classes="sidebar-header")

            with ScrollableContainer(classes="sidebar-scroll"):
                # Server status section
                with Vertical(classes="sidebar-section"):
                    yield Static("🖥️ Serveur", classes="sidebar-section-title")
                    yield ServerStatusWidget(SERVER_IP, id="server-status-widget")

                # Domains section
                with Vertical(classes="sidebar-section"):
                    yield Static("🌐 Domaines", classes="sidebar-section-title")
                    yield from self._build_domain_cards()

                # Quick actions section
                with Vertical(classes="sidebar-section"):
                    yield Static("⚡ Actions Rapides", classes="sidebar-section-title")
                    yield Button("🔄 Rafraîchir", id="btn-refresh", classes="primary-button")
                    yield Button("📋 Logs Apache", id="btn-apache-logs", classes="primary-button")
                    yield Button("🔧 État Services", id="btn-services", classes="primary-button")
                    yield Button("💻 Terminal", id="btn-terminal", classes="primary-button")

    def _compose_main_content(self) -> ComposeResult:
        """Compose the main content area with tabs."""
        with Vertical(classes="main-content"):
            yield Static("📋 Tableau de Bord", classes="content-header")

            with Tabs(id="main-tabs"):
                with TabPane("📊 Vue d'ensemble"):
                    yield from self._compose_overview_tab()

                with TabPane("📋 Logs"):
                    yield from self._compose_logs_tab()

                with TabPane("💻 Terminal"):
                    yield from self._compose_terminal_tab()

                with TabPane("⚙️ Paramètres"):
                    yield from self._compose_settings_tab()

    def _build_domain_cards(self) -> ComposeResult:
        """Build domain information cards as a generator."""
        for domain in DOMAINS:
            info = DOMAIN_INFO.get(domain, self._get_default_domain_info(domain))
            yield DomainCardWidget(domain, info, id=f"domain-{domain.replace('.', '-')}")

    @staticmethod
    def _get_default_domain_info(domain: str) -> dict[str, Any]:
        """Return default domain info structure."""
        return {
            "ip": SERVER_IP,
            "ssl_days": 0,
            "services": ["Web"],
            "spf": "",
            "dkim": "",
            "dmarc": "",
        }

    def _compose_overview_tab(self) -> ComposeResult:
        """Compose the overview tab content."""
        with ScrollableContainer():
            with Vertical(classes="info-panel"):
                yield Static("📈 Statistiques Serveur", classes="info-title")
                yield Static(f"Adresse IP: {SERVER_IP}", classes="info-row")
                yield Static("Uptime: 99.9%", classes="info-row")
                yield Static("CPU: 23%", classes="info-row")
                yield Static("Mémoire: 4.2GB / 8GB", classes="info-row")
                yield Static("Disque: 120GB / 200GB", classes="info-row")

            with Vertical(classes="domain-grid"):
                yield from self._compose_domain_details()

    def _compose_domain_details(self) -> ComposeResult:
        """Compose detailed domain information panels."""
        for domain in DOMAINS[:3]:  # Show details for first 3 domains
            info = DOMAIN_INFO.get(domain, self._get_default_domain_info(domain))
            with Vertical(classes="info-panel"):
                yield Static(f"🌐 {domain}", classes="info-title")
                yield Static(f"IP: {info.get('ip', 'N/A')}", classes="info-row")
                yield Static(f"SSL: {info.get('ssl_days', 0)} jours restants", classes="info-row")

                spf = info.get("spf", "")
                if spf:
                    yield Static(f"SPF: {spf[:50]}...", classes="info-row")

    def _compose_logs_tab(self) -> ComposeResult:
        """Compose the logs tab content."""
        with Vertical():
            yield Static("📋 Journaux Système", classes="content-header")
            with Horizontal():
                for log_type, log_file in LOG_TYPES:
                    yield Button(
                        log_type,
                        id=f"btn-log-{log_type.lower()}",
                        classes="primary-button"
                    )
            yield Log(id="main-log-output", classes="log-output")

    def _compose_terminal_tab(self) -> ComposeResult:
        """Compose the terminal tab content."""
        with Vertical():
            yield Static("💻 Terminal SSH", classes="content-header")
            yield CommandInputWidget("SSH", "ssh")
            yield Log(id="terminal-output", classes="log-output")
            with Horizontal():
                yield Button("Exécuter", id="btn-execute", classes="primary-button")
                yield Button("Effacer", id="btn-clear-terminal", classes="danger-button")

    def _compose_settings_tab(self) -> ComposeResult:
        """Compose the settings tab content."""
        with Vertical():
            yield Static("⚙️ Paramètres de Connexion", classes="content-header")
            with Vertical(classes="info-panel"):
                yield Static("Configuration SSH", classes="info-title")
                yield Static("Hôte:", classes="info-label")
                yield Input(value=self.config.get("host", SERVER_IP), id="input-host")
                yield Static("Utilisateur:", classes="info-label")
                yield Input(value=self.config.get("username", ""), id="input-username")
                yield Static("Mot de passe:", classes="info-label")
                yield Input(
                    value=self.config.get("password", ""),
                    password=True,
                    id="input-password"
                )
                with Horizontal():
                    yield Button("💾 Sauvegarder", id="btn-save-settings", classes="primary-button")
                    yield Button("🔌 Tester Connexion", id="btn-test-connection", classes="primary-button")

    # ==========================================================================
    # Event Handlers
    # ==========================================================================

    def on_mount(self) -> None:
        """Handle application mount event."""
        self._update_status("Application démarrée")
        self._load_initial_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        handlers: dict[str, callable] = {
            "btn-refresh": self._handle_refresh,
            "btn-apache-logs": self._handle_apache_logs,
            "btn-services": self._handle_services,
            "btn-terminal": self._handle_terminal,
            "btn-execute": self._handle_execute,
            "btn-clear-terminal": self._handle_clear_terminal,
            "btn-save-settings": self._handle_save_settings,
            "btn-test-connection": self._handle_test_connection,
        }

        # Handle log type buttons
        if button_id and button_id.startswith("btn-log-"):
            log_type = button_id.replace("btn-log-", "").upper()
            self._handle_log_view(log_type)
            return

        handler = handlers.get(button_id)
        if handler:
            handler()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission events."""
        if event.input.id == "ssh-command-input":
            self._execute_ssh_command(event.value)

    # ==========================================================================
    # Action Handlers
    # ==========================================================================

    def action_refresh(self) -> None:
        """Refresh the dashboard."""
        self._handle_refresh()

    def action_show_history(self) -> None:
        """Show command history."""
        self._show_command_history()

    def action_show_settings(self) -> None:
        """Show settings tab."""
        try:
            tabs = self.query_one("#main-tabs", Tabs)
            tabs.active = 3  # Settings tab
        except Exception:
            pass

    # ==========================================================================
    # Private Methods
    # ==========================================================================

    def _handle_refresh(self) -> None:
        """Handle refresh action."""
        self._update_status("Rafraîchissement...")
        self._refresh_domain_cards()

    @work(exclusive=True, thread=True)
    def _handle_apache_logs(self) -> None:
        """Fetch and display Apache logs."""
        self._update_status("Chargement des logs Apache...")
        try:
            logs = self._fetch_logs("access_log")
            self._display_logs(logs, "Apache")
        except Exception as e:
            self._update_status(f"Erreur: {e}")
        finally:
            self._log_to_history("apache_logs", "Viewed Apache logs")

    def _handle_services(self) -> None:
        """Display services status."""
        self._update_status("Chargement de l'état des services...")
        services_info = self._get_services_status()
        self._display_services(services_info)

    def _handle_terminal(self) -> None:
        """Switch to terminal tab."""
        try:
            tabs = self.query_one("#main-tabs", Tabs)
            tabs.active = 2  # Terminal tab
        except Exception:
            pass

    def _handle_execute(self) -> None:
        """Execute SSH command from input."""
        try:
            command_input = self.query_one("#ssh-command-input", Input)
            command = command_input.value.strip()
            if command:
                self._execute_ssh_command(command)
                command_input.value = ""
        except Exception as e:
            self._update_status(f"Erreur d'exécution: {e}")

    def _handle_clear_terminal(self) -> None:
        """Clear terminal output."""
        try:
            terminal_output = self.query_one("#terminal-output", Log)
            terminal_output.clear()
        except Exception:
            pass

    def _handle_save_settings(self) -> None:
        """Save connection settings."""
        try:
            host = self.query_one("#input-host", Input).value
            username = self.query_one("#input-username", Input).value
            password = self.query_one("#input-password", Input).value

            self.config = {
                "host": host,
                "username": username,
                "password": password,
            }
            save_config(self.config)
            self._update_status("Paramètres sauvegardés avec succès")
        except Exception as e:
            self._update_status(f"Erreur de sauvegarde: {e}")

    @work(exclusive=True, thread=True)
    def _handle_test_connection(self) -> None:
        """Test SSH connection."""
        self._update_status("Test de connexion...")
        try:
            self._connect_ssh()
            self._update_status("✅ Connexion réussie!")
            self._is_connected = True
        except Exception as e:
            self._update_status(f"❌ Échec de connexion: {e}")
            self._is_connected = False

    def _handle_log_view(self, log_type: str) -> None:
        """View specific log type."""
        log_file = next(
            (lf for lt, lf in LOG_TYPES if lt.upper() == log_type),
            "access_log"
        )
        self._update_status(f"Chargement des logs {log_type}...")
        try:
            logs = self._fetch_logs(log_file)
            self._display_logs(logs, log_type)
        except Exception as e:
            self._update_status(f"Erreur: {e}")

    # ==========================================================================
    # SSH Operations
    # ==========================================================================

    def _connect_ssh(self) -> paramiko.SSHClient:
        """Establish SSH connection."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        client.connect(
            hostname=self.config.get("host", SERVER_IP),
            username=self.config.get("username", ""),
            password=self.config.get("password", ""),
            timeout=10,
        )
        self.ssh_client = client
        return client

    def _disconnect_ssh(self) -> None:
        """Close SSH connection."""
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception:
                pass
            finally:
                self.ssh_client = None
                self._is_connected = False

    def _execute_ssh_command(self, command: str) -> None:
        """Execute command via SSH."""
        self._log_to_history(command, "Executed via terminal")

        @work(exclusive=True, thread=True)
        def run_command() -> None:
            try:
                if not self.ssh_client or not self._is_connected:
                    self._connect_ssh()

                if self.ssh_client:
                    stdin, stdout, stderr = self.ssh_client.exec_command(command)
                    output = stdout.read().decode("utf-8")
                    error = stderr.read().decode("utf-8")

                    self._display_terminal_output(output, error)
                    self._log_to_history(command, f"Output: {output[:100]}")
            except Exception as e:
                self._display_terminal_output("", str(e))
                self._log_to_history(command, f"Error: {str(e)[:100]}")

        run_command()

    # ==========================================================================
    # Data Operations
    # ==========================================================================

    def _fetch_logs(self, log_type: str) -> str:
        """Fetch logs from server."""
        # Simulated log data for demo purposes
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"[{timestamp}] [{log_type}] Exemple d'entrée de log\n" * 10

    def _get_services_status(self) -> dict[str, str]:
        """Get services status information."""
        return {
            "Apache": "✅ En cours d'exécution",
            "Nginx": "✅ En cours d'exécution",
            "MySQL": "✅ En cours d'exécution",
            "PHP-FPM": "✅ En cours d'exécution",
            "Postfix": "✅ En cours d'exécution",
            "Dovecot": "✅ En cours d'exécution",
        }

    def _refresh_domain_cards(self) -> None:
        """Refresh domain information cards."""
        try:
            # Rebuild domain cards
            domain_cards = list(self._build_domain_cards())
            # Update would happen here in a real implementation
            self._update_status("Domaines rafraîchis")
        except Exception as e:
            self._update_status(f"Erreur de rafraîchissement: {e}")

    # ==========================================================================
    # Display Methods
    # ==========================================================================

    def _update_status(self, message: str) -> None:
        """Update status display."""
        try:
            status_widget = self.query_one("#server-status", Static)
            status_widget.update(f"Statut: {message}")
        except Exception:
            pass

    def _display_logs(self, logs: str, log_type: str) -> None:
        """Display logs in the log output widget."""
        try:
            log_output = self.query_one("#main-log-output", Log)
            log_output.clear()
            log_output.write(logs)
        except Exception:
            pass

    def _display_services(self, services: dict[str, str]) -> None:
        """Display services status."""
        try:
            log_output = self.query_one("#main-log-output", Log)
            log_output.clear()
            for service, status in services.items():
                log_output.write(f"{service}: {status}\n")
        except Exception:
            pass

    def _display_terminal_output(self, output: str, error: str) -> None:
        """Display terminal output."""
        try:
            terminal_output = self.query_one("#terminal-output", Log)
            if output:
                terminal_output.write(output)
            if error:
                terminal_output.write(f"[ERROR] {error}\n")
        except Exception:
            pass

    def _show_command_history(self) -> None:
        """Display command history in terminal."""
        try:
            terminal_output = self.query_one("#terminal-output", Log)
            terminal_output.clear()
            terminal_output.write("=== Historique des Commandes ===\n\n")

            for entry in reversed(self.command_history[-20:]):
                timestamp = entry.get("timestamp", "N/A")
                command = entry.get("command", "N/A")
                result = entry.get("result", "")
                terminal_output.write(f"[{timestamp}] {command}")
                if result:
                    terminal_output.write(f" → {result}")
                terminal_output.write("\n")
        except Exception:
            pass

    # ==========================================================================
    # History Management
    # ==========================================================================

    def _log_to_history(self, command: str, result: str = "") -> None:
        """
        Log command to history file.

        Args:
            command: The command that was executed
            result: The result or status of the command
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "result": result,
        }
        self.command_history.append(entry)
        save_history(self.command_history)

    # ==========================================================================
    # Lifecycle
    # ==========================================================================

    def _load_initial_data(self) -> None:
        """Load initial data on startup."""
        if self.command_history:
            self._update_status(f"{len(self.command_history)} commandes dans l'historique")

    def on_unmount(self) -> None:
        """Handle application unmount event."""
        self._disconnect_ssh()
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

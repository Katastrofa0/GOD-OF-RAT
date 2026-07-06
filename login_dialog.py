import sys
import os
import json
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(__file__)


class LoginDialog(QDialog):
    def __init__(self, default_ip=None, default_port=None, default_token=None, default_aes_key=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GodOfRAT")
        self.setFixedWidth(480)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint)
        
        self.default_ip = default_ip
        self.default_port = default_port
        self.default_token = default_token
        self.default_aes_key = default_aes_key
        
        self.base_dir = get_base_dir()
        self.config_file = os.path.join(self.base_dir, "controller_config.json")
        
        self.icon_path = resource_path(os.path.join("icons", "rat_ico.png"))
        self.word_path = resource_path(os.path.join("icons", "word.png"))
        
        if os.path.exists(self.icon_path):
            self.setWindowIcon(QIcon(self.icon_path))
        
        self.load_settings()
        self.init_ui()
        
    def _safe_str(self, value):

        if value is None or value is ...:
            return ""
        return str(value)
        
    def load_settings(self):

        self.saved_ip = "127.0.0.1"
        self.saved_port = "8081"
        self.saved_token = ""
        self.saved_aes_key = ""
        self.saved_remember = False
        self.saved_aes_enabled = False
        
        
        if self.default_token is not None and self.default_token is not ...:
            self.saved_token = str(self.default_token)
        if self.default_ip is not None and self.default_ip is not ...:
            self.saved_ip = str(self.default_ip)
        if self.default_port is not None and self.default_port is not ...:
            self.saved_port = str(self.default_port)
        if self.default_aes_key is not None and self.default_aes_key is not ...:
            self.saved_aes_key = str(self.default_aes_key)
            self.saved_aes_enabled = True
        

        try:
           
            has_args = any([
                self.default_ip is not None and self.default_ip is not ...,
                self.default_port is not None and self.default_port is not ...,
                self.default_token is not None and self.default_token is not ...,
                self.default_aes_key is not None and self.default_aes_key is not ...
            ])
            
            if not has_args and os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                    ip_val = config.get("ip")
                    self.saved_ip = self._safe_str(ip_val) if ip_val is not None else "127.0.0.1"
                    
                    port_val = config.get("port")
                    self.saved_port = self._safe_str(port_val) if port_val is not None else "8081"
                    
                    token_val = config.get("token")
                    self.saved_token = self._safe_str(token_val) if token_val is not None else ""
                    
                    aes_val = config.get("aes_key")
                    self.saved_aes_key = self._safe_str(aes_val) if aes_val is not None else ""
                    
                    self.saved_aes_enabled = bool(config.get("aes_enabled", False))
                    self.saved_remember = bool(config.get("remember", False))
        except Exception as e:
            print(f"Error loading config: {e}")
        
    def init_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; }
            QLabel { color: #666666; font-size: 11px; letter-spacing: 0.5px; }
            QLineEdit {
                background-color: #0a0a0a;
                border: 1px solid #2a2a2a;
                padding: 8px 10px;
                font-family: 'Consolas';
                font-size: 12px;
                color: #cccccc;
            }
            QLineEdit:focus { border: 1px solid #555555; }
            QCheckBox { color: #666666; font-size: 11px; }
            QCheckBox::indicator { width: 12px; height: 12px; border: 1px solid #2a2a2a; background-color: #0a0a0a; }
            QCheckBox::indicator:checked { background-color: #800000; border: 1px solid #800000; }
            QPushButton {
                background-color: #0f0f0f;
                border: 1px solid #2a2a2a;
                padding: 8px 20px;
                font-size: 11px;
                color: #888888;
            }
            QPushButton:hover { background-color: #1a1a1a; border: 1px solid #555555; color: #cccccc; }
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(30, 15, 30, 25)
        
        # HEADER
        header_container = QLabel()
        canvas_w, canvas_h = 500, 230
        pixmap = QPixmap(canvas_w, canvas_h)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        if os.path.exists(self.icon_path):
            logo = QPixmap(self.icon_path)
            l_size = 85
            logo_scaled = logo.scaled(l_size, l_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((canvas_w - logo_scaled.width()) // 2, 0, logo_scaled)
        
        if os.path.exists(self.word_path):
            word_img = QPixmap(self.word_path)
            w_width = 480
            word_scaled = word_img.scaled(w_width, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((canvas_w - word_scaled.width()) // 2, 80, word_scaled)
        
        painter.end()
        header_container.setPixmap(pixmap)
        header_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(header_container)
        self.main_layout.addSpacing(10)
        
        # FIELDS
        self.main_layout.addWidget(QLabel("server"))
        self.ip_input = QLineEdit()
        self.ip_input.setText(self.saved_ip)
        self.main_layout.addWidget(self.ip_input)
        
        self.main_layout.addWidget(QLabel("port"))
        self.port_input = QLineEdit()
        self.port_input.setText(self.saved_port)
        self.main_layout.addWidget(self.port_input)
        
        self.main_layout.addWidget(QLabel("token"))
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setText(self.saved_token)
        self.main_layout.addWidget(self.token_input)
        
        self.main_layout.addSpacing(5)
        
        self.aes_checkbox = QCheckBox("AES Encryption")
        self.aes_checkbox.setChecked(self.saved_aes_enabled)
        self.aes_checkbox.toggled.connect(self.on_aes_toggled)
        self.main_layout.addWidget(self.aes_checkbox)
        
        self.aes_key_input = QLineEdit()
        self.aes_key_input.setPlaceholderText("AES Secret Key")
        self.aes_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.aes_key_input.setVisible(self.saved_aes_enabled)
        self.aes_key_input.setText(self.saved_aes_key)
        self.main_layout.addWidget(self.aes_key_input)

        self.ssl_checkbox = QCheckBox("SSL/TLS (wss://)")
        self.ssl_checkbox.setChecked(False)
        self.main_layout.addWidget(self.ssl_checkbox)
        
        self.remember_checkbox = QCheckBox("remember settings")
        self.remember_checkbox.setChecked(self.saved_remember)
        self.main_layout.addWidget(self.remember_checkbox)
        
        self.main_layout.addStretch()
        
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.connect_btn = QPushButton("connect")
        self.connect_btn.setStyleSheet("""
            QPushButton { background-color: #800000; border: 1px solid #800000; color: white; font-weight: bold; }
            QPushButton:hover { background-color: #600000; border: 1px solid #600000; }
        """)
        self.connect_btn.clicked.connect(self.on_connect)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.connect_btn)
        self.main_layout.addLayout(btn_layout)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #800000; font-size: 10px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.status_label)

    def on_aes_toggled(self, checked):
        self.aes_key_input.setVisible(checked)
        self.adjustSize()

    def save_settings(self):
        if not self.remember_checkbox.isChecked():
            return
        config = {
            "ip": self.ip_input.text(),
            "port": int(self.port_input.text()) if self.port_input.text().isdigit() else 8081,
            "token": self.token_input.text(),
            "aes_key": self.aes_key_input.text() if self.aes_checkbox.isChecked() else "",
            "aes_enabled": self.aes_checkbox.isChecked(),
            "remember": True
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def on_connect(self):
        ip = self.ip_input.text().strip()
        port = self.port_input.text().strip()
        token = self.token_input.text().strip()
        
        if not ip or not token:
            self.status_label.setText("fill all fields")
            return
        
        try:
            self.server_port = int(port)
            self.server_ip = ip
            self.auth_token = token
            self.aes_key = self.aes_key_input.text().strip() if self.aes_checkbox.isChecked() else None
            self.use_ssl = self.ssl_checkbox.isChecked()
            self.save_settings()
            self.accept()
        except Exception:
            self.status_label.setText("invalid port")

    def get_connection_info(self):
        return {
            "ip": self.server_ip,
            "port": self.server_port,
            "token": self.auth_token,
            "aes_key": self.aes_key,
            "use_ssl": self.use_ssl
        }
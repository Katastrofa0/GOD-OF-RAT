import asyncio
import base64
import json
import os
import uuid
import websockets
from PyQt6.QtCore import QThread, pyqtSignal, QTimer


class TransferWorker(QThread):

    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, server_ip, server_port, agent_id, transfer_uuid=None):
        super().__init__()
        self.server_ip = server_ip
        self.server_port = server_port
        self.agent_id = agent_id
        self.transfer_uuid = transfer_uuid or str(uuid.uuid4())
        self._is_cancelled = False
        self.loop = None
        self.chunk_size = 4 * 1024 * 1024

    def cancel(self):
        self._is_cancelled = True
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._cancel_async(), self.loop)

    async def _cancel_async(self):
        pass

    def run(self):
        asyncio.run(self._run_async())

    async def _run_async(self):
        self.loop = asyncio.get_running_loop()
        await self._transfer()

    async def _transfer(self):
        raise NotImplementedError


class UploadWorker(TransferWorker):
    def __init__(self, server_ip, server_port, agent_id, local_file, remote_path, parent_ws, crypto=None):
        super().__init__(server_ip, server_port, agent_id)
        self.local_file = local_file
        self.remote_path = remote_path
        self.parent_ws = parent_ws
        self.crypto = None  
        self.ws = None
        self.loop = None

    def run(self):

        try:
            asyncio.run(self._run_async())
        except Exception as e:
            self.finished.emit(False, f"[-] Upload worker crashed: {str(e)}")

    async def _transfer(self):
        try:
            self.status.emit(f" Uploading {os.path.basename(self.local_file)}...")
            total_size = os.path.getsize(self.local_file)

            self.parent_ws.send_cmd("upload", {
                "path": self.remote_path,
                "transfer_uuid": self.transfer_uuid
            }, target=self.agent_id)

            await asyncio.sleep(0.5)

            protocol = "wss" if getattr(self.parent_ws, 'use_ssl', False) else "ws"
            uri = f"{protocol}://{self.server_ip}:{self.server_port}"
            
            kwargs = {"max_size": 524288000, "ping_interval": 30, "ping_timeout": 120}
            if getattr(self.parent_ws, 'use_ssl', False):
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                kwargs["ssl"] = ssl_context
            
            async with websockets.connect(uri, **kwargs) as ws:
                self.ws = ws  
                self.loop = asyncio.get_running_loop() 

                init_packet = {
                    "action": "init_file_transfer",
                    "transfer_uuid": self.transfer_uuid,
                    "role": "controller"
                }
                await ws.send(json.dumps(init_packet))
                self.status.emit("[+] File channel opened, sending data...")

                uploaded = 0
                chunk_size = 512 * 1024 
                with open(self.local_file, "rb") as f:
                    while True:
                        if self._is_cancelled:
                            break
                        chunk = await asyncio.to_thread(f.read, chunk_size)
                        if not chunk:
                            break
                        await ws.send(chunk)
                        uploaded += len(chunk)
                        progress = int(uploaded * 100 / total_size) if total_size else 0
                        self.progress.emit(progress)

                if self._is_cancelled:
                    self.finished.emit(False, "[!] Upload cancelled by user")
                    return

                await ws.send(json.dumps({"type": "transfer_done"}))
                self.status.emit("[...] Waiting for agent confirmation...")

                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=120.0)
                    if isinstance(response, str):
                        resp_data = json.loads(response)
                        if resp_data.get("type") == "file_received" and resp_data.get("status") == "success":
                            self.finished.emit(True, f"[+++] Upload completed: {os.path.basename(self.local_file)}")
                        else:
                            error = resp_data.get("error", "Unknown error")
                            self.finished.emit(False, f"[-] Agent error: {error}")
                    else:
                        self.finished.emit(False, "[-] Unexpected response from agent")
                except asyncio.TimeoutError:
                    self.finished.emit(False, "[...] Timeout waiting for agent confirmation")

        except Exception as e:
            self.finished.emit(False, f"[-] Upload error: {str(e)}")


class DownloadWorker(TransferWorker):
    def __init__(self, server_ip, server_port, agent_id, remote_path, local_dir, parent_ws, crypto=None):
        super().__init__(server_ip, server_port, agent_id)
        self.remote_path = remote_path
        self.local_dir = local_dir
        self.filename = os.path.basename(remote_path)
        self.local_path = os.path.join(local_dir, self.filename)
        self.parent_ws = parent_ws
        self.crypto = None
        self.ws = None
        self.loop = None
        self._write_buffer = bytearray()

    async def _write_buffered(self, data):
        self._write_buffer.extend(data)
        if len(self._write_buffer) >= self.chunk_size:
            to_write = bytes(self._write_buffer)
            self._write_buffer.clear()
            await asyncio.to_thread(self._write_to_file, to_write)

    def _write_to_file(self, data):
        with open(self.local_path, "ab") as f:
            f.write(data)

    async def _transfer(self):
        try:
            self.status.emit(f"📥 Downloading {self.filename}...")
            os.makedirs(self.local_dir, exist_ok=True)

            with open(self.local_path, "wb") as f:
                pass

            self.parent_ws.send_cmd("download", {
                "path": self.remote_path,
                "transfer_uuid": self.transfer_uuid
            }, target=self.agent_id)

            await asyncio.sleep(0.5)

            protocol = "wss" if getattr(self.parent_ws, 'use_ssl', False) else "ws"
            uri = f"{protocol}://{self.server_ip}:{self.server_port}"
            
            kwargs = {"max_size": 524288000, "ping_interval": 30, "ping_timeout": 60}
            if getattr(self.parent_ws, 'use_ssl', False):
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                kwargs["ssl"] = ssl_context
            
            async with websockets.connect(uri, **kwargs) as ws:
                self.ws = ws
                self.loop = asyncio.get_running_loop()
                init_packet = {
                    "action": "init_file_transfer",
                    "transfer_uuid": self.transfer_uuid,
                    "role": "controller"
                }
                await ws.send(json.dumps(init_packet))
                await asyncio.sleep(0.5)

                total_size = None
                received = 0
                last_progress = 0

                async for message in ws:
                    if self._is_cancelled:
                        break

                    if isinstance(message, bytes):
                        self._write_buffer.extend(message)
                        received += len(message)

                        if len(self._write_buffer) >= self.chunk_size:
                            to_write = bytes(self._write_buffer)
                            self._write_buffer.clear()
                            await asyncio.to_thread(self._write_to_file, to_write)

                        if total_size:
                            progress = int(received * 100 / total_size)
                            if progress - last_progress >= 2 or progress == 100:
                                self.progress.emit(progress)
                                last_progress = progress

                    elif isinstance(message, str):
                        try:
                            msg_data = json.loads(message)
                            if msg_data.get("type") == "file_size":
                                total_size = msg_data.get("size", 0)
                            elif msg_data.get("type") == "transfer_done":
                                break
                        except:
                            pass

                if self._write_buffer and not self._is_cancelled:
                    to_write = bytes(self._write_buffer)
                    self._write_buffer.clear()
                    await asyncio.to_thread(self._write_to_file, to_write)

                if not self._is_cancelled and os.path.exists(self.local_path) and os.path.getsize(self.local_path) > 0:
                    self.finished.emit(True, f"[+] Download completed: {self.local_path}")
                elif not self._is_cancelled:
                    self.finished.emit(False, "[-] Download failed: file is empty")
                else:
                    if os.path.exists(self.local_path):
                        os.remove(self.local_path)
                    self.finished.emit(False, "[!] Download cancelled")

        except Exception as e:
            if os.path.exists(self.local_path):
                try:
                    os.remove(self.local_path)
                except:
                    pass
            self.finished.emit(False, f"[-] Download error: {str(e)}")


class TDataDownloadWorker(DownloadWorker):
    def __init__(self, server_ip, server_port, agent_id, remote_path, local_dir, parent_ws, crypto=None, filename=None):
        super().__init__(server_ip, server_port, agent_id, remote_path, local_dir, parent_ws, crypto)
        if filename:
            self.filename = filename
            self.local_path = os.path.join(local_dir, filename)

    async def _transfer(self):
        try:
            self.status.emit(f" Downloading TData from {self.remote_path}...")
            os.makedirs(self.local_dir, exist_ok=True)

            with open(self.local_path, "wb") as f:
                pass

            self.parent_ws.send_cmd("download_tdata", {
                "path": self.remote_path,
                "transfer_uuid": self.transfer_uuid
            }, target=self.agent_id)

            await asyncio.sleep(0.5)

            protocol = "wss" if getattr(self.parent_ws, 'use_ssl', False) else "ws"
            uri = f"{protocol}://{self.server_ip}:{self.server_port}"
            
            kwargs = {"max_size": 524288000, "ping_interval": 30, "ping_timeout": 60}
            if getattr(self.parent_ws, 'use_ssl', False):
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                kwargs["ssl"] = ssl_context

            
            async with websockets.connect(uri, **kwargs) as ws:
                init_packet = {
                    "action": "init_file_transfer",
                    "transfer_uuid": self.transfer_uuid,
                    "role": "controller"
                }
                await ws.send(json.dumps(init_packet))
                await asyncio.sleep(0.5)

                total_size = None
                received = 0
                last_progress = 0

                async for message in ws:
                    if self._is_cancelled:
                        break

                    if isinstance(message, bytes):
                        self._write_buffer.extend(message)
                        received += len(message)

                        if len(self._write_buffer) >= self.chunk_size:
                            to_write = bytes(self._write_buffer)
                            self._write_buffer.clear()
                            await asyncio.to_thread(self._write_to_file, to_write)

                        if total_size:
                            progress = int(received * 100 / total_size)
                            if progress - last_progress >= 2 or progress == 100:
                                self.progress.emit(progress)
                                last_progress = progress

                    elif isinstance(message, str):
                        try:
                            msg_data = json.loads(message)
                            if msg_data.get("type") == "file_size":
                                total_size = msg_data.get("size", 0)
                            elif msg_data.get("type") == "transfer_done":
                                break
                        except:
                            pass

                if self._write_buffer and not self._is_cancelled:
                    to_write = bytes(self._write_buffer)
                    self._write_buffer.clear()
                    await asyncio.to_thread(self._write_to_file, to_write)

                if not self._is_cancelled and os.path.exists(self.local_path) and os.path.getsize(self.local_path) > 0:
                    self.finished.emit(True, f"[+++] TData download completed: {self.local_path}")
                elif not self._is_cancelled:
                    self.finished.emit(False, "[-] Download failed: file is empty")
                else:
                    if os.path.exists(self.local_path):
                        os.remove(self.local_path)
                    self.finished.emit(False, "[-] Download cancelled")

        except Exception as e:
            if os.path.exists(self.local_path):
                try:
                    os.remove(self.local_path)
                except:
                    pass
            self.finished.emit(False, f"[-] Download error: {str(e)}")
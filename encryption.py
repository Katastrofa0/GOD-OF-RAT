import base64
import hashlib
import secrets
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

class AESCrypto:

    
    def __init__(self, key: str = None):
        self.key = None
        if key:
            self.set_key(key)
    
    def set_key(self, key: str):

        self.key = hashlib.sha256(key.encode('utf-8')).digest()
    
    def encrypt(self, data: str) -> str:

        if not self.key:
            return data
        
        iv = secrets.token_bytes(16)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        padded_data = pad(data.encode('utf-8'), AES.block_size)
        encrypted = cipher.encrypt(padded_data)
        combined = iv + encrypted
        result = base64.b64encode(combined).decode('utf-8')
        # print(f"[AES] Encrypted {len(data)} bytes -> {len(result)} chars")  #
        return result

    def decrypt(self, encrypted_data: str) -> str:

        if not self.key:
            return encrypted_data
        
        try:
            raw = base64.b64decode(encrypted_data)
            iv = raw[:16]
            encrypted = raw[16:]
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
            result = decrypted.decode('utf-8')
            # print(f"[AES] Decrypted {len(encrypted_data)} chars -> {len(result)} bytes")  #
            return result
        except Exception as e:
            print(f"[AES] Decrypt failed: {e}")
            raise ValueError(f"Decryption failed: {e}")
    
    def encrypt_bytes(self, data: bytes) -> bytes:
        if not self.key:
            return data
        
        iv = secrets.token_bytes(16)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        padded_data = pad(data, AES.block_size)
        encrypted = cipher.encrypt(padded_data)
        return iv + encrypted
    
    def decrypt_bytes(self, data: bytes) -> bytes:
        if not self.key:
            return data
        
        iv = data[:16]
        encrypted = data[16:]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
        return decrypted

server_crypto = AESCrypto()
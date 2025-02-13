# gestor/ring.py
import socket
import time
import json
import random
from termcolor import colored
from .logging import log_message
from .config import SERVER_PORT, RING_UPDATE_INTERVAL, TIMEOUT,FIX_FINGERS_INTERVAL, CHECK_PREDECESSOR_INTERVAL,CHECK_SUCCESSOR_INTERVAL
from .global_state import my_node_id, local_ip

finger_table=[]
predecessor=None
successor=None
current=None
connected=0
M=32
events=set()

#region ring_init
def  ring_init():
    global predecessor,successor,current 
    current={"id": my_node_id, "ip": local_ip, "port": SERVER_PORT}
    predecessor=current
    successor=current

#region print_ft
def print_ft():
    print(colored('__________________________','yellow'))
    print(colored(f'<< {predecessor}','yellow'))
    print(colored(f'>> {successor}','yellow'))
    for node in finger_table:
        if node['id']==my_node_id:
            break;
        print(colored(f"{node['id']} {node['ip']}",'yellow'))
    print(colored('__________________________','yellow'))

#region hash
def hash(key: str) -> int:
    """
    Calcula un hash polinomial simple de la cadena 'key' y lo reduce módulo ID_SPACE.
    """
    h = 0
    for ch in key:
        h = (h * 31 + ord(ch)) % (2**M)
    return h

#region in_interval
def in_interval(val: int, start: int, end: int, inclusive_end: bool = False) -> bool:
    """
    Determina si 'val' se encuentra en el intervalo circular (start, end).
    Si inclusive_end es True, el intervalo es (start, end].
    Se asume el espacio de identificadores (módulo ID_SPACE).
    """
    if start < end:
        return (start < val <= end) if inclusive_end else (start < val < end)
    else:
        return (val > start or val <= end) if inclusive_end else (val > start or val < end)


#region closest_preceding_finger
def closest_preceding_finger(id_val: int) -> dict:
    """
    Recorre la finger table en orden inverso y retorna el nodo cuya ID sea
    el más cercano (precedente) a id_val, pero mayor que este nodo.
    Si no se encuentra, retorna el propio nodo.
    """
    global finger_table, my_node_id
    for entry in reversed(finger_table):
        node = entry["node"]
        if in_interval(node["id"], my_node_id, id_val, inclusive_end=False):
            return node
    return {"id": my_node_id, "ip": local_ip, "port": SERVER_PORT}


#region find_successor
def find_successor(id_val,event=-1,hard_mode=False):
    
    if event!=-1 and event in events:
       return {}
    events.add(event)
    
    
    global my_node_id, successor, predecessor

    if my_node_id == successor["id"]:
        return current
    
    if in_interval(id_val, my_node_id, successor["id"], inclusive_end=True):
        return successor
    else:
        if hard_mode:
            for node in finger_table:
                try:    
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(TIMEOUT)
                        s.connect((node["ip"], node["port"]))
                        msg = {"action": "find_successor", "id": id_val,"hard_mode":1,"event":event}
                        s.sendall(json.dumps(msg).encode())
                        resp = s.recv(4096)
                        if resp:
                            result = json.loads(resp.decode())
                            if len(result):
                                return result
                except Exception as e:
                    log_message(colored(f"[Chord] Error en find_successor RPC a nodo {node['id']}: {e}", "red"))
                    return {}
        else:
            next_node = closest_preceding_finger(id_val)
            if next_node["id"] == my_node_id:
                return successor
            try:    
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(TIMEOUT)
                    s.connect((next_node["ip"], next_node["port"]))
                    msg = {"action": "find_successor", "id": id_val,"hard_mode":0,"event":event}
                    s.sendall(json.dumps(msg).encode())
                    resp = s.recv(4096)
                    if resp:
                        result = json.loads(resp.decode())
                        return result
            except Exception as e:
                log_message(colored(f"[Chord] Error en find_successor RPC a nodo {next_node['id']}: {e}", "red"))
                return {}


#region find_predecessor
def find_predecessor(id_val,event=-1,hard_mode=False):
    if event!=-1 and event in events:
       return {}
    events.add(event)
    
    global my_node_id, successor, predecessor

    if my_node_id == successor["id"] or in_interval(id_val, my_node_id, successor["id"], inclusive_end=True):
        # Only one node or in the interval with the successor
        return current
    else:
        if hard_mode:
            for node in finger_table:
                try:    
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(TIMEOUT)
                        s.connect((node["ip"], node["port"]))
                        msg = {"action": "find_predecessor", "id": id_val,"hard_mode":1,"event":event}
                        s.sendall(json.dumps(msg).encode())
                        resp = s.recv(4096)
                        if resp:
                            result = json.loads(resp.decode())
                            if len(result):
                                return result
                except Exception as e:
                    log_message(colored(f"[Chord] Error en find_predecessor RPC a nodo {node['id']}: {e}", "red"))
                    return {}
        else:
            next_node = closest_preceding_finger(id_val)
            if next_node["id"] == my_node_id:
                return next_node
            try:    
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(TIMEOUT)
                    s.connect((next_node["ip"], next_node["port"]))
                    msg = {"action": "find_predecessor", "id": id_val,"hard_mode":0,"event":event}
                    s.sendall(json.dumps(msg).encode())
                    resp = s.recv(4096)
                    if resp:
                        result = json.loads(resp.decode())
                        return result
            except Exception as e:
                log_message(colored(f"[Chord] Error en find_predecessor RPC a nodo {next_node['id']}: {e}", "red"))
                return {}

#region nodes_connected()
def nodes_connected(event=-1):
    if event!=-1 and event in events:
       return 0
    events.add(event)
    
    ans=1
    try:    
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            s.connect((successor["ip"], successor["port"]))
            msg = {"action": "nodes_connected","event":event}
            s.sendall(json.dumps(msg).encode())
            resp = s.recv(4096)
            if resp:
                result = json.loads(resp.decode())
                ans+=result['number']
    except Exception as e:
        log_message(colored(f"[Chord] Error calculando la cantidad de nodos conectados: {e}", "red"))
        return 0
    return ans

#region update_successor
def update_successor(node,new_successor):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            s.connect((node["ip"], node["port"]))
            msg = {"action": "update_successor", "node": new_successor}
            s.sendall(json.dumps(msg).encode())
            resp = s.recv(4096)
    except Exception as e:
        log_message(colored(f"[Chord] Error updateando el sucesor: {e}", "red"))


#region update_predecessor
def update_predecessor(node,new_predecessor):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            s.connect((node["ip"], node["port"]))
            msg = {"action": "update_predecessor", "node":new_predecessor}
            s.sendall(json.dumps(msg).encode())
            resp = s.recv(4096)
    except Exception as e:
        log_message(colored(f"[Chord] Error updateando el predecesor: {e}", "red"))


#region update_next
def update_next(i,event):
    if event!=-1 and event in events:
       return {}
    events.add(event)
    print(colored(f">> Updating next {i}",'red'))
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            s.connect((successor["ip"], successor["port"]))
            msg = {"action": "update", "i": i,"event":event}
            
            s.sendall(json.dumps(msg).encode())
            resp = s.recv(4096)
            print(colored(f">> Response {resp}",'red'))
            
        update_finger_table(i,event)
    except Exception as e:
        log_message(colored(f"[Chord] Error updateando el anillo: {e}", "red"))


#region update_ring
def update_ring():
    global connected
    connected=nodes_connected(random.randint(1,1000000000))
    print(colored(f"NODES CONNECTED: {connected}",'cyan'))
    
    for i in range(1,M):
        if connected-1<2**i:
            break    
        print(colored(f'Sending update on bit {i}','red'))
        event=random.randint(1,1000000000)
        update_next(i,event)





#region update_finger_table
def update_finger_table(i,event):
    print(colored(f">> Updating FT on  {i}",'red'))
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            print(colored(f">> Connectin {finger_table[i-1]["ip"]}",'red'))
            s.connect((finger_table[i-1]["ip"], finger_table[i-1]["port"]))
            msg = {"action": "ask", "i": i-1}
            s.sendall(json.dumps(msg).encode())
            resp = s.recv(4096)
            resp=json.loads(resp.decode())
            
            print(colored(f">> Response  {resp}",'red'))
            if resp['id']=="-1":
                return      
            
            if len(finger_table)==i:
                finger_table.append(resp)
            else:
                finger_table[i]=resp
    except Exception as e:
        log_message(colored(f"[Chord] Error updateando el finger_table: {e}", "red"))
        


#region join
def join(existing_node: dict):
    global successor,predecessor
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            s.connect((existing_node["ip"], existing_node["port"]))
            msg = {"action": "join", "id": my_node_id}
            s.sendall(json.dumps(msg).encode())
            resp = s.recv(4096)
            if resp:
                resp = json.loads(resp.decode())
                succ=resp['successor']
                pred=resp['predecessor']
                successor = succ
                predecessor = pred
                update_successor(predecessor,current)
                update_predecessor(successor,current)

                print(colored(resp,'magenta'))
                finger_table.append(successor)
                log_message(colored(f"[Chord] Nodo unido al anillo. Sucesor asignado: {successor['id']}", "green"))

    except Exception as e:
        log_message(colored(f"[Chord] Error en join() con nodo existente: {e}. Se arranca como nodo inicial.", "red"))
        predecessor = current
        successor = current



def fix_fingers():
    pass

def stabilize():    
    pass

def check_predecessor():
    pass

def check_successor():
    pass

#region chord_handler
def chord_handler(request: dict) -> dict:
    global successor,predecessor
    action = request.get("action")

    if action == "join":
        id_val = request.get("id")
        print(colored(f"Joining node {id_val}",'green'))
        rs = find_successor(id_val,random.randint(1,1000000000),1)
        rp = find_predecessor(id_val,random.randint(1,1000000000),1)
        return {"successor":rs,"predecessor":rp}
    
    if action == "find_successor":
        id_val = request.get("id")
        event = request.get("event")
        hard_mode =  request.get("hard_mode")
        result = find_successor(id_val,event,hard_mode)
        return result
    if action == "find_predecessor":
        id_val = request.get("id")
        event = request.get("event")
        hard_mode =  request.get("hard_mode")
        result = find_predecessor(id_val,event,hard_mode)
        return result
    
    if action=="update_successor":
        successor=request.get("node")
        if len(finger_table):
            finger_table[0]=successor
        else: 
            finger_table.append(successor)
        print_ft()
        return {}
    if action=="update_predecessor":
        predecessor=request.get("node")
        print_ft()
        return {}
    
    if action == "ask":
        i=request.get('i')
        if(i>len(finger_table)):
            return {'id':"-1"}
        return finger_table[i]
    
    if action =='update':
        i=request.get('i')
        event=request.get('event')
        update_next(i,event)
        print_ft()
        return {}
    
    if action =='nodes_connected':
        event=request.get('event')
        ans=nodes_connected(event)
        return {"number":ans}

    elif action == "ping":
        return {"status": "alive"}
    else:
        return {"status": "error", "message": f"Acción desconocida en chord_handler: {action}"}


#region run_stabilize
def run_stabilize():
    while True:
        stabilize()
        time.sleep(RING_UPDATE_INTERVAL)

#region run_fix_fingers
def run_fix_fingers():
    while True:
        update_ring()
        print_ft()
        time.sleep(FIX_FINGERS_INTERVAL)

#region run_check_predecessor
def run_check_predecessor():
    while True:
        check_predecessor()
        time.sleep(CHECK_PREDECESSOR_INTERVAL)
#region run_check_sccessor
def run_check_successor():
    while True:
        check_successor()
        time.sleep(CHECK_SUCCESSOR_INTERVAL)

#region start_chord_maintenance
def start_chord_maintenance():
    """
    Lanza en hilos separados las funciones de estabilización, fix_fingers y check_predecessor.
    """
    import threading
    threading.Thread(target=run_stabilize, daemon=True).start()
    threading.Thread(target=run_fix_fingers, daemon=True).start()
    threading.Thread(target=run_check_predecessor, daemon=True).start()
    threading.Thread(target=run_check_successor, daemon=True).start()
    log_message(colored("[Chord] Mantenimiento del anillo iniciado (stabilize, fix_fingers, check_predecessor).", "magenta"))

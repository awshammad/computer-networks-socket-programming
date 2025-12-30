# server.py
import socket
import threading
import random
import time

# ─── Configuration ─────────────────────────────────────────────────────────────
SERVER_HOST   = '0.0.0.0'
TCP_PORT      = 6000
UDP_PORT      = 6001

MIN_PLAYERS   = 2
MAX_PLAYERS   = 4
SUBROUNDS     = 6
SUB_DURATION  = 10     # seconds per round
RANGE_LOW     = 1
RANGE_HIGH    = 100

# ─── Global State ──────────────────────────────────────────────────────────────
clients    = {}    # username -> tcp_conn
udp_addrs  = {}    # username -> (ip, udp_port)
lock       = threading.Lock()

def broadcast_tcp(msg: str):
    with lock:
        for conn in list(clients.values()):
            try:
                conn.sendall(msg.encode())
            except:
                pass

def accept_joins(tcp_sock, target_count, timeout=None):
    """
    Fill `clients` until we have target_count or timeout expires.
    If timeout is None, block indefinitely.
    """
    if timeout is not None:
        tcp_sock.settimeout(timeout)
    try:
        while len(clients) < target_count:
            conn, addr = tcp_sock.accept()
            conn.sendall(f"Enter your username: ({len(clients)}/{MAX_PLAYERS}):\n".encode())
            data = conn.recv(1024).decode().strip().split()
            if len(data)==2 and data[0].upper()=="JOIN":
                name = data[1]
                with lock:
                    if name in clients:
                        conn.sendall(b"Username taken\n")
                        conn.close()
                        continue
                    clients[name] = conn
                conn.sendall(f"Connected as {name}\n".encode())
                # UDP handshake
                conn.sendall(b"SEND_UDP_PORT <port>\n")
                parts = conn.recv(1024).decode().split()
                if len(parts)==2 and parts[0]=="SEND_UDP_PORT":
                    udp_addrs[name] = (addr[0], int(parts[1]))
                else:
                    udp_addrs[name] = (addr[0], UDP_PORT)
                broadcast_tcp(f"{name} joined ({len(clients)}/{MAX_PLAYERS})\n")
            else:
                conn.sendall(b"Invalid. Enter username:\n")
                conn.close()
    except socket.timeout:
        pass
    finally:
        tcp_sock.settimeout(None)

def run_one_game():
    """
    Runs one secret-number game of up to SUBROUNDS × SUB_DURATION seconds.
    Returns True if players want to start another game, False otherwise.
    """
    secret = random.randint(RANGE_LOW, RANGE_HIGH)
    broadcast_tcp(
        "\n=== NEW GAME ===\n"
        f"{len(clients)} players, secret is 1–100.\n"
        f"{SUBROUNDS} rounds × {SUB_DURATION}s each, one UDP guess per round.\n"
    )
    print(f"[Server] Secret number is {secret}")

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind((SERVER_HOST, UDP_PORT))

    winner = None

    # play up to SUBROUNDS
    for rnd in range(1, SUBROUNDS+1):
        if not clients or winner:
            break

        broadcast_tcp(f"\n--- Round {rnd}/{SUBROUNDS} ---\n")
        round_start = time.time()
        guessed = set()

        while time.time() - round_start < SUB_DURATION and not winner:
            udp_sock.settimeout((round_start + SUB_DURATION) - time.time())
            try:
                data, addr = udp_sock.recvfrom(1024)
            except socket.timeout:
                break
            except ConnectionResetError:
                # client closed its UDP socket; ignore and keep waiting
                continue

            msg = data.decode().strip()
            user = next((u for u,a in udp_addrs.items() if a == addr), None)
            if not user or user in guessed:
                continue
            guessed.add(user)

            if msg.lower() == 'exit':
                udp_sock.sendto(b"You exited mid-game.\n", addr)
                with lock:
                    clients.pop(user, None)
                    udp_addrs.pop(user, None)
                broadcast_tcp(f"{user} left mid-game.\n")

                # If exactly one player remains, give them the choice:
                if len(clients) == 1:
                    lone = next(iter(clients))
                    lone_conn = clients[lone]
                    lone_conn.sendall(b"You're alone now. Continue? (yes/no)\n")
                    try:
                        ans = lone_conn.recv(1024).decode().strip().lower()
                    except:
                        ans = 'no'

                    if ans == 'yes':
                        broadcast_tcp(f"{lone} chose to continue alone.\n")
                        # break out of this round so we jump to the next for-loop iteration
                        break
                    else:
                        broadcast_tcp(f"{lone} chose to end the game.\n")
                        udp_sock.close()
                        return False

                # otherwise (0 or >1 remain), just continue this round
                continue
            
            # try to parse an integer guess
            try:
                val = int(msg)
            except ValueError:
                udp_sock.sendto(
                    b"Invalid guess. Enter a number between 1 and 100. Your chance this round is over.\n",
                    addr
                )
            if val < RANGE_LOW or val > RANGE_HIGH:
                udp_sock.sendto(
                    b"Invalid guess. Enter a number between 1 and 100. Your chance this round is over.\n",
                    addr
                )
                continue
            if val < secret:
                udp_sock.sendto(b"Try HIGHER\n", addr)
            elif val > secret:
                udp_sock.sendto(b"Try LOWER\n", addr)
            else:
                udp_sock.sendto(b"CORRECT!\n", addr)
                winner = user
                break

    udp_sock.close()

    # announce result
    if winner:
        print(f"[Server] Game over. Winner: {winner} (secret was {secret})")
        broadcast_tcp(f"\n🎉 {winner} guessed it! Secret was {secret}.\n")
    else:
        print(f"[Server] Game over. No winner (secret was {secret})")
        broadcast_tcp(f"\nNo one guessed it. Secret was {secret}.\n")

    # prompt for next game
    broadcast_tcp("Start a new round? (yes/no)\n")

    # collect yes/no from each remaining player
    responses = {}
    with lock:
        survivors = list(clients.items())
    for name, conn in survivors:
        try:
            ans = conn.recv(1024).decode().strip().lower()
        except:
            ans = 'no'
        responses[name] = ans

    # if any say "yes", restart
    if any(v=='yes' for v in responses.values()):
        broadcast_tcp("\n▶️ Starting next round...\n")
        return True
    else:
        broadcast_tcp("\n❌ No more rounds. Goodbye!\n")
        return False

if __name__ == "__main__":
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.bind((SERVER_HOST, TCP_PORT))
    tcp.listen(MAX_PLAYERS)
    print(f"[Server] Listening TCP {TCP_PORT}, UDP {UDP_PORT}")

    while True:
        # 1) initial join (block for 2 players)
        print(f"[Server] Waiting for at least {MIN_PLAYERS} players...")
        accept_joins(tcp, MIN_PLAYERS)

        # 2) late-join window (up to 4 players total)
        print(f"[Server] Late-join window (15s) up to {MAX_PLAYERS} players total")
        accept_joins(tcp, MAX_PLAYERS, timeout=15)

        # ─── NEW: show waiting list ───────────────────────────────
        waiting_list = ", ".join(clients.keys())
        print(f"[Server] Players ready to start: {waiting_list}")
        broadcast_tcp(f"\nWaiting list: {waiting_list}\n")
        # ────────────────────────────────────────────────────────────

        # 3) play games back-to-back until everyone says "no" or all leave
        keep_playing = True
        while keep_playing and clients:
            keep_playing = run_one_game()

        # 4) clean up all connections, then go back to step 1
        with lock:
            for c in clients.values():
                try: c.close()
                except: pass
            clients.clear()
            udp_addrs.clear()

        print("[Server] Session ended; ready for new players.\n")

# client.py
import socket
import threading

TCP_PORT = 6000
UDP_PORT = 6001

def recv_tcp(sock):
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                break
            print(data.decode(), end='')
        except:
            break

def recv_udp(sock):
    while True:
        try:
            data, _ = sock.recvfrom(1024)
            print(data.decode(), end='')
        except:
            break

def stdin_loop(tcp_sock, udp_sock, server_ip):
    while True:
        try:
            line = input()
        except EOFError:
            break
        txt = line.strip()
        if not txt:
            continue
        if txt.lower() in ('yes','no'):
            tcp_sock.sendall((txt+"\n").encode())
        else:
            udp_sock.sendto(txt.encode(), (server_ip, UDP_PORT))
            if txt.lower() == 'exit':
                break

if __name__ == "__main__":
    server_ip = input("Server IP: ").strip()
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.connect((server_ip, TCP_PORT))

    # JOIN handshake
    print(tcp.recv(1024).decode(), end='')
    while True:
        name = input("JOIN > ").strip()
        tcp.sendall(f"JOIN {name}\n".encode())
        resp = tcp.recv(1024).decode()
        print(resp, end='')
        if resp.startswith("Connected as"):
            break

    # UDP port handshake
    prompt = tcp.recv(1024).decode()
    print(prompt, end='')
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("", 0))
    tcp.sendall(f"SEND_UDP_PORT {udp.getsockname()[1]}\n".encode())
    print("UDP ready on port", udp.getsockname()[1])

    # start threads
    threading.Thread(target=recv_tcp, args=(tcp,), daemon=True).start()
    threading.Thread(target=recv_udp, args=(udp,), daemon=True).start()

    # read stdin and dispatch
    stdin_loop(tcp, udp, server_ip)

    tcp.close()
    udp.close()
    print("Client exiting.")

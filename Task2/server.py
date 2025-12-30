import socket
import os
from datetime import datetime

# Server Configuration
HOST = '0.0.0.0'    # Listen on all network interfaces
PORT = 9956         # Amir's Id = 1222596 => XY = 56

# Supported MIME Types Mapping
MIME_TYPES = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.mp4': 'video/mp4',
}

# Get MIME type based on file extension
def get_content_type(file_path):
    ext = os.path.splitext(file_path)[1]
    return MIME_TYPES.get(ext, 'application/octet-stream')  # Default to binary stream

# Build HTTP Response based on status code and content
def build_response(status_code, content=b"", content_type="text/html", redirect_location=None):
    status_messages = {
        200: "OK",
        404: "Not Found",
        307: "Temporary Redirect",
    }

    # Prepare status line
    header = f"HTTP/1.1 {status_code} {status_messages[status_code]}\r\n"

    # Handle redirection if needed
    if status_code == 307 and redirect_location:
        header += f"Location: {redirect_location}\r\n\r\n"
        return header.encode()

    # Standard headers for successful responses
    header += f"Content-Type: {content_type}\r\n"
    header += f"Content-Length: {len(content)}\r\n"
    header += "Connection: close\r\n\r\n"

    return header.encode() + content

# Handle client request and send appropriate response
def handle_request(conn, addr):
    try:
        # Receive and decode client request
        request = conn.recv(1024).decode()
        print(f"[{datetime.now()}] Request from {addr[0]}:{addr[1]} to server port {PORT}")
        print(f"Request details:\n{request}\n{'-'*50}")

        # Parse requested path or fallback to root
        try:
            path = request.split(" ")[1]
        except:
            path = "/"

        # Handle language-specific or root paths
        if path in ["/", "/en", "/index.html", "/main_en.html"]:
            file_path = "html/main_en.html"
        elif path in ["/ar", "/main_ar.html"]:
            file_path = "html/main_ar.html"
        # Handle dynamic redirection for /handle?filename=
        elif path.startswith("/handle?filename="):
            filename = path.split("filename=")[-1]
            ext = os.path.splitext(filename)[-1].lower()
            # Redirect to Google Video or Image search based on file type
            if ext == ".mp4":
                redirect_url = f"https://www.google.com/search?q={filename}&tbm=vid"
            else:
                redirect_url = f"https://www.google.com/search?q={filename}&tbm=isch"
            response = build_response(307, redirect_location=redirect_url)
            conn.sendall(response)
            conn.close()
            return
        else:
            # Clean the path and attempt to locate the file
            file_path = path.strip("/")
            if not os.path.isfile(file_path):
                file_path = "html" + path

        # Send file content if exists
        if os.path.isfile(file_path):
            with open(file_path, "rb") as f:
                content = f.read()
            response = build_response(200, content, get_content_type(file_path))
            print(f"Response: 200 OK - Serving {file_path}")
        else:
            # Send 404 Not Found response with client details
            html = f"""
            <html>
            <head>
                <title>Error 404</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    .error {{ color: red; font-size: 24px; }}
                    .details {{ margin-top: 20px; }}
                </style>
            </head>
            <body>
                <h1 class="error">Error 404! The file is not found</h1>
                <div class="details">
                    <p>Client IP: {addr[0]}</p>
                    <p>Client Port: {addr[1]}</p>
                    <p>Server Port: {PORT}</p>
                </div>
            </body>
            </html>
            """
            response = build_response(404, html.encode())
            print(f"Response: 404 Not Found - Requested file not found")
        
        # Send the prepared response to the client
        conn.sendall(response)
    except Exception as e:
        print("Error handling request:", e)
    finally:
        conn.close()

# Start the server and wait for incoming connections
def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((HOST, PORT))
        server.listen(5)
        print(f"🌐 Server running at http://localhost:{PORT}/")
        print(f"Server port: {PORT}")

        # Handle incoming client connections indefinitely
        while True:
            conn, addr = server.accept()
            handle_request(conn, addr)

# Run server when script is executed directly
if __name__ == "__main__":
    start_server()

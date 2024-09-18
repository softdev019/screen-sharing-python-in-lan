import tkinter as tk
from tkinter import simpledialog, messagebox
import threading
import pyautogui
import pyaudio
import cv2
import numpy as np
import zmq

class ScreenShareApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Screen Share App")
        self.geometry("300x150")

        self.label = tk.Label(self, text="Choose an option")
        self.label.pack(pady=20)

        self.server_button = tk.Button(self, text="Server", command=self.run_server)
        self.server_button.pack(side=tk.LEFT, padx=20)

        self.client_button = tk.Button(self, text="Join", command=self.run_client)
        self.client_button.pack(side=tk.RIGHT, padx=20)

    def run_server(self):
        port = simpledialog.askinteger("Port", "Enter port number:")
        if port:
            self.destroy()
            server = Server(port)
            server.start()

    def run_client(self):
        server_ip = simpledialog.askstring("Server IP", "Enter Server IP (use 'localhost' for local):")
        port = simpledialog.askinteger("Port", "Enter port number:")
        if server_ip and port:
            if server_ip.lower() == "localhost":
                server_ip = "127.0.0.1"
            self.destroy()
            client = Client(server_ip, port)
            client.start()

class Server:
    def __init__(self, port):
        self.port = port
        self.context = zmq.Context()
        self.screen_socket = self.context.socket(zmq.PUB)
        self.audio_socket = self.context.socket(zmq.PUB)
        self.screen_socket.bind(f"tcp://*:{self.port}")
        self.audio_socket.bind(f"tcp://*:{self.port + 1}")
        print(f"Server started on port {self.port} for screen, {self.port + 1} for audio, waiting for connections...")

    def start(self):
        screen_thread = threading.Thread(target=self.capture_screen)
        audio_thread = threading.Thread(target=self.capture_audio)

        screen_thread.start()
        audio_thread.start()

        screen_thread.join()
        audio_thread.join()

    def capture_screen(self):
        while True:
            screenshot = pyautogui.screenshot()
            frame = np.array(screenshot)
            _, buffer = cv2.imencode('.jpg', frame)
            self.screen_socket.send(buffer.tobytes())
            print(f"Sent frame of size: {len(buffer)}")

    def capture_audio(self):
        chunk = 1024
        format = pyaudio.paInt16
        channels = 1
        rate = 44100
        p = pyaudio.PyAudio()

        stream = p.open(format=format,
                        channels=channels,
                        rate=rate,
                        input=True,
                        frames_per_buffer=chunk)

        while True:
            data = stream.read(chunk)
            self.audio_socket.send(data)
            print("Sent audio chunk")

class Client:
    def __init__(self, server_ip, port):
        self.server_ip = server_ip
        self.port = port
        self.context = zmq.Context()
        self.screen_socket = self.context.socket(zmq.SUB)
        self.audio_socket = self.context.socket(zmq.SUB)
        self.screen_socket.connect(f"tcp://{self.server_ip}:{self.port}")
        self.audio_socket.connect(f"tcp://{self.server_ip}:{self.port + 1}")
        self.screen_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.audio_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        print(f"Connecting to server at {self.server_ip}:{self.port} for screen, {self.server_ip}:{self.port + 1} for audio")

    def start(self):
        self.running = True
        screen_thread = threading.Thread(target=self.receive_screen)
        audio_thread = threading.Thread(target=self.receive_audio)

        screen_thread.start()
        audio_thread.start()

        screen_thread.join()
        audio_thread.join()

    def receive_screen(self):
        while self.running:
            try:
                buffer = self.screen_socket.recv()
                if len(buffer) < 10:  # Arbitrary threshold to check for valid image data
                    continue

                frame = np.frombuffer(buffer, dtype=np.uint8)
                frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)
                if frame is not None:
                    cv2.imshow('Screen', frame)
                    cv2.waitKey(1)
                else:
                    print("Failed to decode frame")
            except zmq.error.ContextTerminated:
                break
            except Exception as e:
                print(f"Failed to receive screen data: {e}")

    def receive_audio(self):
        chunk = 1024
        format = pyaudio.paInt16
        channels = 1  # Match the number of channels with the server
        rate = 44100
        p = pyaudio.PyAudio()

        stream = p.open(format=format,
                        channels=channels,
                        rate=rate,
                        output=True)

        while self.running:
            try:
                data = self.audio_socket.recv()
                stream.write(data)
            except zmq.error.ContextTerminated:
                break
            except Exception as e:
                print(f"Failed to receive audio data: {e}")

    def reconnect(self):
        print("Reconnecting to server...")
        self.running = False
        time.sleep(1)  # Wait before reconnecting
        self.context.destroy()
        self.context = zmq.Context()
        self.screen_socket = self.context.socket(zmq.SUB)
        self.audio_socket = self.context.socket(zmq.SUB)
        self.screen_socket.connect(f"tcp://{self.server_ip}:{self.port}")
        self.audio_socket.connect(f"tcp://{self.server_ip}:{self.port + 1}")
        self.screen_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.audio_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.running = True
        self.start()

if __name__ == "__main__":
    app = ScreenShareApp()
    app.mainloop()

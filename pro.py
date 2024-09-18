import tkinter as tk
from tkinter import simpledialog, messagebox
import threading
import pyautogui
import cv2, os
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import psutil, socket, sys, pystray,zmq
class ScreenShareApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Screen Share App")
        
        if getattr(sys, 'frozen', False):
            # we are running in a bundle
            bundle_dir = sys._MEIPASS
        else:
            # we are running in a normal Python environment
            bundle_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(bundle_dir, 'icon.ico')
        self.iconbitmap(icon_path)
        self.geometry("200x350")
        self.label = tk.Label(self, text="Choose an IP to Join")
        self.label.pack(pady=10)

        self.ip_listbox = tk.Listbox(self, selectmode=tk.SINGLE)
        self.ip_listbox.pack(pady=10)
        ips = ["192.168.2.204", "192.168.2.205", "192.168.2.206", "192.168.2.207", "192.168.2.208"]
        for ip in ips:
            self.ip_listbox.insert(tk.END, ip)
        self.ip_listbox.bind("<Double-Button-1>", self.on_double_click)
        self.join_button = tk.Button(self, text="Join", command=self.run_client)
        self.join_button.pack(pady=10)

        self.server_button = tk.Button(self, text="Host", command=self.run_server)
        self.server_button.pack(pady=10)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.tray_icon = None
        self.client = None
        self.server = None
        self.create_tray_icon()
    def get_ethernet_ip(self):
        interfaces = psutil.net_if_addrs()
        for interface, addrs in interfaces.items():
            if interface == 'Ethernet':
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        return addr.address
        return None
    
    def run_server(self):
        ip_address = self.get_ethernet_ip()
        if not ip_address:
            messagebox.showerror("Error", "Could not find Ethernet adapter IP address")
            return

        last_octet = int(ip_address.split('.')[-1])
        port = int(f"{last_octet % 10}{last_octet % 10}{last_octet % 10}{last_octet % 10}")
        port = simpledialog.askinteger("Port", "Enter port number:", initialvalue=port)
        print(port)
        if port:
            self.destroy()
            server = Server(port)
            server.start()

    def run_client(self):
        selected_ip = self.ip_listbox.get(tk.ACTIVE)
        
        if selected_ip:
            last_octet = int(selected_ip.split('.')[-1])
            port = int(f"{last_octet % 10}{last_octet % 10}{last_octet % 10}{last_octet % 10}")
            port = simpledialog.askinteger("Port", "Enter port number:", initialvalue=port)
            if(port == None):
                return
            self.destroy()
            self.client = Client(selected_ip, port)
            self.client.start()
        else:
            server_ip = simpledialog.askstring("Server IP", "Enter Server IP (use 'localhost' for local):")
            port = simpledialog.askinteger("Port", "Enter port number:")
            
            
            if server_ip and port != None:
                if server_ip.lower() == "localhost":
                    server_ip = "127.0.0.1"
                self.destroy()
                self.client = Client(server_ip, port)
                self.client.start()
    def on_double_click(self, event):
        self.run_client()
    def on_closing(self):
        self.close_all()

    def create_tray_icon(self):
        # Create an image for the tray icon
        image = Image.new('RGB', (64, 64), color='blue')
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 64, 64), outline='blue', fill='blue')

        self.tray_icon = pystray.Icon("ScreenShareApp", image, "Screen Share App", menu=pystray.Menu(
            pystray.MenuItem("Open", self.show_window),
            pystray.MenuItem("Close", self.close_all)
        ))
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self):
        self.deiconify()

    def close_all(self, icon=None, item=None):
        if self.client:
            self.client.close()
        if self.server:
            self.server.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        self.quit()
        self.destroy()
        sys.exit()
class Server:
    def __init__(self, port):
        self.port = port
        self.context = zmq.Context()
        self.screen_socket = self.context.socket(zmq.PUB)
        self.screen_socket.bind(f"tcp://*:{self.port}")
        self.running = False
        print(f"Server started on port {self.port}, waiting for connections...")

    def start(self):
        screen_thread = threading.Thread(target=self.capture_screen)
        screen_thread.start()
        screen_thread.join()

    def capture_screen(self):
        while True:
            screenshot = pyautogui.screenshot()
            frame = np.array(screenshot)
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # Convert to grayscale
            _, buffer = cv2.imencode('.jpg', gray_frame)
            self.screen_socket.send(buffer.tobytes())
            print(f"Sent frame of size: {len(buffer)}")
            
    def stop(self):
        self.running = False
        self.context.term()
        print("Server stopped")
class Client:
    def __init__(self, server_ip, port):
        self.server_ip = server_ip
        self.port = port
        self.context = zmq.Context()
        self.screen_socket = self.context.socket(zmq.SUB)
        self.screen_socket.connect(f"tcp://{self.server_ip}:{self.port}")
        self.screen_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.running = False
        print(f"Connecting to server at {self.server_ip}:{self.port}")

        self.root = tk.Tk()
        self.root.title("Shared Screen")
        self.root.attributes('-topmost', True)  # Make window stay on top

        self.canvas = tk.Canvas(self.root, bg='black')
        self.scroll_x = tk.Scrollbar(self.root, orient='horizontal', command=self.canvas.xview)
        self.scroll_y = tk.Scrollbar(self.root, orient='vertical', command=self.canvas.yview)

        self.canvas.configure(xscrollcommand=self.scroll_x.set, yscrollcommand=self.scroll_y.set)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.scroll_x.grid(row=1, column=0, sticky='ew')
        self.scroll_y.grid(row=0, column=1, sticky='ns')

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.do_drag)
        self.canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind_all("<Shift-MouseWheel>", self.on_shift_mouse_wheel)

        self.img_id = None
        self.drag_start_x = 0
        self.drag_start_y = 0

    def start(self):
        self.running = True
        self.screen_thread = threading.Thread(target=self.receive_screen)
        self.screen_thread.start()
        self.root.mainloop()

    def receive_screen(self):
        while self.running:
            try:
                buffer = self.screen_socket.recv()
                if len(buffer) < 10:  # Arbitrary threshold to check for valid image data
                    continue

                frame = np.frombuffer(buffer, dtype=np.uint8)
                frame = cv2.imdecode(frame, cv2.IMREAD_GRAYSCALE)  # Decode as grayscale
                if frame is not None:
                    self.update_image(frame)
                else:
                    print("Failed to decode frame")
            except zmq.error.ContextTerminated:
                break
            except Exception as e:
                print(f"Failed to receive screen data: {e}")

    def update_image(self, frame):
        img = Image.fromarray(frame)
        img_tk = ImageTk.PhotoImage(image=img)

        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))
        if self.img_id is None:
            self.img_id = self.canvas.create_image(0, 0, anchor='nw', image=img_tk)
        else:
            self.canvas.itemconfig(self.img_id, image=img_tk)
        self.canvas.image = img_tk

    def start_drag(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def do_drag(self, event):
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        self.canvas.xview_scroll(int(-dx), "units")
        self.canvas.yview_scroll(int(-dy), "units")
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def on_mouse_wheel(self, event):
        self.canvas.yview_scroll(-int(event.delta / 120), "units")

    def on_shift_mouse_wheel(self, event):
        self.canvas.xview_scroll(-int(event.delta / 120), "units")

    def close(self):
        self.running = False
        self.context.term()
        if self.screen_thread.is_alive():
            self.screen_thread.join()
        self.root.quit()
        self.root.destroy()

if __name__ == "__main__":
    app = ScreenShareApp()
    app.mainloop()

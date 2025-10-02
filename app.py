import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog, filedialog, messagebox, Text, font
import paramiko
import threading
import queue
import time
import json
import os
import sys
from datetime import datetime
import re  # For stripping ANSI escape sequences
import select  # For better handling of channel readiness
from PIL import ImageTk, Image  # For image handling; install pillow if needed: pip install pillow
import shutil  # For copying files

# Define base directory for user data (writable without admin)
if os.name == 'nt':  # Windows
    base_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~\\AppData\\Roaming')), 'CommandForge')
else:
    base_dir = os.path.expanduser('~/.commandforge')  # Fallback for non-Windows
os.makedirs(base_dir, exist_ok=True)

# Class to manage a single SSH session
class SSHSession:
    def __init__(self, host, port, user, passw, output_text, log_path):
        # Store connection details and UI elements
        self.host = host
        self.port = port
        self.user = user
        self.passw = passw
        self.output_text = output_text  # Tkinter Text widget for output
        
        # Set up SSH client
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(host, port=port, username=user, password=passw)
        
        # Invoke an interactive shell with terminal type
        self.channel = self.client.invoke_shell(term='vt100', width=80, height=24)
        self.connected = True
        
        # Queue for thread-safe output handling
        self.output_queue = queue.Queue()
        
        # Start reader thread to handle incoming output
        self.reader_thread = threading.Thread(target=self._reader, daemon=True)
        self.reader_thread.start()
        
        # Open log file for automatic saving
        self.logfile = open(log_path, 'a')

    def _reader(self):
        # Thread loop to read from SSH channel continuously
        while self.connected:
            # Use select to wait for data ready with timeout
            r, w, e = select.select([self.channel], [], [self.channel], 0.1)
            if self.channel in r:
                data = self.channel.recv(4096)
                if not data:
                    break
                decoded = data.decode('utf-8', errors='replace')
                # Strip OSC sequences (like title sets ending with \x07 or ST)
                decoded = re.sub(r'\x1b\].*?(\x07|\x1b\\)', '', decoded)
                # Strip other ANSI escape sequences
                decoded = re.sub(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', decoded)
                # Remove non-printable characters except \n, \t, \r
                decoded = ''.join(c for c in decoded if c.isprintable() or c == '\n' or c == '\t' or c == '\r')
                # Handle line endings: replace CRLF with LF, and standalone CR with LF
                decoded = decoded.replace('\r\n', '\n').replace('\r', '\n')
                self.output_queue.put(decoded)
            if self.channel in e:
                # Handle error if needed
                break
        # If loop exits, connection is lost
        self.connected = False
        self.output_queue.put("\nConnection lost. Press Send (or Enter) to reconnect.\n")

    def send(self, cmd):
        # Handle reconnect if needed
        if not self.connected:
            try:
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.client.connect(self.host, port=self.port, username=self.user, password=self.passw)
                self.channel = self.client.invoke_shell(term='vt100', width=80, height=24)
                self.connected = True
                self.reader_thread = threading.Thread(target=self._reader, daemon=True)
                self.reader_thread.start()
                self.output_queue.put("Reconnected.\n")
            except Exception as e:
                self.output_queue.put(f"Reconnect failed: {str(e)}\n")
                return
        # Send the command to the SSH channel with CRLF for Windows compatibility
        self.channel.send(cmd + '\r\n')

    def interrupt(self):
        # Send Ctrl+C interrupt if connected
        if self.connected:
            self.channel.send('\x03')

    def close(self):
        # Clean up resources
        if self.connected:
            self.client.close()
        self.logfile.close()

# Main application setup
root = tk.Tk()
root.title("Command Forge")
root.geometry("1200x600")  # Increased width for reference pane

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    icon_path = os.path.join(sys._MEIPASS, 'command_forge.ico')
else:
    icon_path = 'command_forge.ico'
root.iconbitmap(icon_path)

# Theme settings
themes = {
    'light': {
        'bg': 'white',
        'fg': 'black',
        'button_bg': 'lightgray',
        'button_fg': 'black',
        'text_bg': 'white',
        'text_fg': 'black',
        'notebook_bg': 'white',
        'interrupt_bg': 'red',
        'interrupt_fg': 'white',
        'check_select': 'white'
    },
    'dark': {
        'bg': '#2e2e2e',
        'fg': 'white',
        'button_bg': '#4d4d4d',
        'button_fg': 'white',
        'text_bg': '#1e1e1e',
        'text_fg': 'white',
        'notebook_bg': '#2e2e2e',
        'interrupt_bg': '#8b0000',
        'interrupt_fg': 'white',
        'check_select': '#1e1e1e'
    }
}
current_theme = 'light'  # Default

# Load theme preference if exists
settings_path = os.path.join(base_dir, 'settings.json')
try:
    with open(settings_path, 'r') as f:
        settings = json.load(f)
        current_theme = settings.get('theme', 'light')
except FileNotFoundError:
    pass

def apply_theme(widget, theme):
    if isinstance(widget, tk.Tk) or isinstance(widget, tk.Toplevel):
        widget.config(bg=themes[theme]['bg'])
    elif isinstance(widget, (tk.Frame, ttk.Frame)):
        widget.config(bg=themes[theme]['bg'])
    elif isinstance(widget, (tk.Label, ttk.Label)):
        widget.config(bg=themes[theme]['bg'], fg=themes[theme]['fg'])
    elif isinstance(widget, (tk.Button, ttk.Button)):
        if 'Interrupt' in widget.cget('text'):
            widget.config(bg=themes[theme]['interrupt_bg'], fg=themes[theme]['interrupt_fg'])
        else:
            widget.config(bg=themes[theme]['button_bg'], fg=themes[theme]['button_fg'])
    elif isinstance(widget, tk.Entry):
        widget.config(bg=themes[theme]['text_bg'], fg=themes[theme]['fg'], insertbackground=themes[theme]['fg'])
    elif isinstance(widget, Text):
        widget.config(bg=themes[theme]['text_bg'], fg=themes[theme]['text_fg'], insertbackground=themes[theme]['fg'])
    elif isinstance(widget, tk.Listbox):
        widget.config(bg=themes[theme]['text_bg'], fg=themes[theme]['fg'])
    elif isinstance(widget, tk.Checkbutton):
        widget.config(bg=themes[theme]['bg'], fg=themes[theme]['fg'], selectcolor=themes[theme]['check_select'], activebackground=themes[theme]['bg'], activeforeground=themes[theme]['fg'])
    elif isinstance(widget, ttk.Combobox):
        widget.config(background=themes[theme]['text_bg'], foreground=themes[theme]['fg'])
    elif isinstance(widget, ttk.Notebook):
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TNotebook", background=themes[theme]['notebook_bg'])
        style.configure("TNotebook.Tab", background=themes[theme]['button_bg'], foreground=themes[theme]['button_fg'])
        style.map("TNotebook.Tab", background=[("selected", themes[theme]['bg'])],
                  foreground=[("selected", themes[theme]['fg'])])
    # Recurse for children
    for child in widget.winfo_children():
        apply_theme(child, theme)

def switch_theme(new_theme):
    global current_theme
    current_theme = new_theme
    with open(settings_path, 'w') as f:
        json.dump({'theme': new_theme}, f)
    apply_theme(root, new_theme)
    # Apply to all open Toplevel windows
    for win in root.winfo_children():
        if isinstance(win, tk.Toplevel):
            apply_theme(win, new_theme)
    # Apply to session tabs
    for tab in session_notebook.tabs():
        frame = root.nametowidget(tab)
        apply_theme(frame, new_theme)

# PanedWindow for main content (left) and reference (right)
paned = tk.PanedWindow(root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
paned.pack(fill='both', expand=True)

# Left frame for commands and sessions
left_frame = tk.Frame(paned)
paned.add(left_frame, minsize=600)

# Right frame for reference
right_frame = tk.Frame(paned)
paned.add(right_frame, minsize=300)
reference_label = tk.Label(right_frame, text="Reference", font=("Arial", 12, "bold"))
reference_label.pack(anchor='w')
reference_scroll = tk.Scrollbar(right_frame)
reference_scroll.pack(side='right', fill='y')
reference_text = Text(right_frame, wrap='word', yscrollcommand=reference_scroll.set)
reference_text.pack(fill='both', expand=True)
reference_scroll.config(command=reference_text.yview)
reference_text.tag_config('bold', font=font.Font(weight="bold"))
reference_text.tag_config('italic', font=font.Font(slant="italic"))
reference_images = []  # To keep references to images

# Notebook for custom command categories (top section in left)
commands_notebook = ttk.Notebook(left_frame)
commands_notebook.pack(fill='both', expand=False)

# Checkboxes frame
checkbox_frame = tk.Frame(left_frame)
checkbox_frame.pack(anchor='w')

# Checkbox for auto-send
auto_send_var = tk.BooleanVar(value=False)
auto_send_check = tk.Checkbutton(checkbox_frame, text="Auto-send commands", variable=auto_send_var)
auto_send_check.pack(side='left')

# Checkbox for dark mode
dark_mode_var = tk.BooleanVar(value=(current_theme == 'dark'))
def toggle_dark_mode():
    switch_theme('dark' if dark_mode_var.get() else 'light')
dark_mode_check = tk.Checkbutton(checkbox_frame, text="Dark Mode", variable=dark_mode_var, command=toggle_dark_mode)
dark_mode_check.pack(side='left')

# Checkbox for hiding reference pane
hide_reference_var = tk.BooleanVar(value=False)
def toggle_reference():
    paned.paneconfigure(right_frame, hide=hide_reference_var.get())
hide_reference_check = tk.Checkbutton(checkbox_frame, text="Hide Reference", variable=hide_reference_var, command=toggle_reference)
hide_reference_check.pack(side='left')

# Notebook for SSH session tabs (bottom section in left, expandable)
session_notebook = ttk.Notebook(left_frame)
session_notebook.pack(fill='both', expand=True)

# Create images directory if not exists
os.makedirs(os.path.join(base_dir, 'images'), exist_ok=True)

# Load custom commands from JSON
commands_path = os.path.join(base_dir, 'commands.json')
def load_commands():
    global commands
    try:
        with open(commands_path, 'r') as f:
            commands = json.load(f)
    except FileNotFoundError:
        commands = {}  # If file missing, start empty
    # Ensure structure
    for cat in commands:
        commands[cat] = {'commands': commands[cat].get('commands', commands[cat] if isinstance(commands[cat], dict) else {}),
                         'reference': commands[cat].get('reference', {'text': '', 'images': []})}
    rebuild_commands_notebook()

def rebuild_commands_notebook():
    for i in range(commands_notebook.index("end")):
        commands_notebook.forget(0)
    for category, data in commands.items():
        cat_frame = tk.Frame(commands_notebook)
        cat_frame.pack(fill='both', expand=True)
        cat_frame.buttons = []
        for btn_name, cmd in data.get('commands', {}).items():
            btn = tk.Button(cat_frame, text=btn_name, command=lambda c=cmd: (send_custom_command(c) if auto_send_var.get() else insert_custom_command(c)))
            cat_frame.buttons.append(btn)
        commands_notebook.add(cat_frame, text=category)
        cat_frame.bind("<Configure>", wrap_buttons)
    commands_notebook.bind("<<NotebookTabChanged>>", update_reference)

def wrap_buttons(event):
    frame = event.widget
    width = event.width
    row = 0
    col = 0
    current_x = 0
    for btn in frame.buttons:
        btn.grid_forget()
        req_width = btn.winfo_reqwidth() + 10  # Add padding
        if current_x + req_width > width and col > 0:
            row += 1
            col = 0
            current_x = 0
        btn.grid(row=row, column=col, sticky='w')
        col += 1
        current_x += req_width

def update_reference(event):
    selected_tab = commands_notebook.select()
    if not selected_tab:
        return
    category = commands_notebook.tab(selected_tab, "text")
    reference = commands.get(category, {}).get('reference', {'text': '', 'images': []})
    reference_text.delete('1.0', tk.END)
    global reference_images
    reference_images = []  # Clear previous images
    text = reference.get('text', '')
    # Simple formatting: **bold**, *italic*
    lines = text.split('\n')
    for line in lines:
        parts = re.split(r'(\*\*.*?\*\*)|(\*.*?\*)', line)
        for part in parts:
            if part and part.startswith('**') and part.endswith('**'):
                reference_text.insert(tk.END, part[2:-2], 'bold')
            elif part and part.startswith('*') and part.endswith('*'):
                reference_text.insert(tk.END, part[1:-1], 'italic')
            else:
                reference_text.insert(tk.END, part)
        reference_text.insert(tk.END, '\n')
    images = reference.get('images', [])
    for img_path in images:
        try:
            img = Image.open(img_path)
            img = img.resize((200, 200))  # Resize for display
            photo = ImageTk.PhotoImage(img)
            reference_text.image_create(tk.END, image=photo)
            reference_text.insert(tk.END, '\n')
            reference_images.append(photo)  # Keep reference
        except Exception as e:
            reference_text.insert(tk.END, f"[Error loading image: {str(e)}]\n")

load_commands()

# Dictionary to map tab frames to SSHSession objects, entries, and histories
sessions = {}
entries = {}
histories = {}  # {frame: {'list': [], 'index': -1}}

def insert_custom_command(cmd):
    # Get the current active tab and insert command into its input box
    current_tab = session_notebook.select()
    if not current_tab:
        return
    frame = root.nametowidget(current_tab)
    ent = entries.get(frame)
    if ent:
        ent.delete(0, tk.END)
        ent.insert(0, cmd)

def send_custom_command(cmd):
    # Get the current active tab and send command to its session
    current_tab = session_notebook.select()
    if not current_tab:
        return
    frame = root.nametowidget(current_tab)
    session = sessions.get(frame)
    if session:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        session.output_text.insert(tk.END, f"[{timestamp}] Sent: {cmd}\n")
        session.output_text.see(tk.END)
        session.send(cmd)

# Function to process output queues for all sessions (called repeatedly)
def process_queues():
    for session in sessions.values():
        try:
            while True:
                output = session.output_queue.get_nowait()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                session.output_text.insert(tk.END, f"[{timestamp}] Received:\n{output}")
                session.output_text.see(tk.END)  # Auto-scroll to end
                session.logfile.write(output)  # Auto-save to log
                session.logfile.flush()
        except queue.Empty:
            pass
    root.after(100, process_queues)  # Schedule next check

# Start processing queues
process_queues()

# Load saved connections if exists
connections_path = os.path.join(base_dir, 'connections.json')
saved_connections = []
try:
    with open(connections_path, 'r') as f:
        saved_connections = json.load(f)
except FileNotFoundError:
    pass

# Function to add a new SSH session tab
def add_new_session(host=None, user=None, port=None, name=None, passw=None):
    if passw is None:
        # Create a custom dialog for input
        dialog = tk.Toplevel(root)
        dialog.title("New Connection")
        dialog.geometry("300x300")
        dialog.grab_set()  # Make modal
        apply_theme(dialog, current_theme)

        tk.Label(dialog, text="Name (optional):").grid(row=0, column=0, padx=5, pady=5)
        name_entry = tk.Entry(dialog)
        name_entry.grid(row=0, column=1, padx=5, pady=5)
        if name:
            name_entry.insert(0, name)

        tk.Label(dialog, text="Host:").grid(row=1, column=0, padx=5, pady=5)
        host_entry = tk.Entry(dialog)
        host_entry.grid(row=1, column=1, padx=5, pady=5)
        if host:
            host_entry.insert(0, host)

        tk.Label(dialog, text="Port:").grid(row=2, column=0, padx=5, pady=5)
        port_entry = tk.Entry(dialog)
        port_entry.grid(row=2, column=1, padx=5, pady=5)
        port_entry.insert(0, port or "22")

        tk.Label(dialog, text="User:").grid(row=3, column=0, padx=5, pady=5)
        user_entry = tk.Entry(dialog)
        user_entry.grid(row=3, column=1, padx=5, pady=5)
        if user:
            user_entry.insert(0, user)

        tk.Label(dialog, text="Password:").grid(row=4, column=0, padx=5, pady=5)
        passw_entry = tk.Entry(dialog, show='*')
        passw_entry.grid(row=4, column=1, padx=5, pady=5)

        save_var = tk.BooleanVar(value=False)
        save_check = tk.Checkbutton(dialog, text="Save this connection", variable=save_var)
        save_check.grid(row=5, column=0, columnspan=2, pady=5)

        def submit():
            nonlocal host, user, port, name, passw
            name = name_entry.get()
            host = host_entry.get()
            port_str = port_entry.get()
            port = int(port_str) if port_str else 22
            user = user_entry.get()
            passw = passw_entry.get()
            if host and user and passw:
                if save_var.get() and not name:
                    name = simpledialog.askstring("Connection Name", "Enter a name for this connection:")
                    if not name:
                        return
                dialog.destroy()
                create_session(host, port, user, passw, name)
                if save_var.get():
                    conn = {"name": name, "host": host, "port": port, "user": user, "password": passw}
                    if conn not in saved_connections:
                        saved_connections.append(conn)
                        with open(connections_path, 'w') as f:
                            json.dump(saved_connections, f)
            else:
                messagebox.showwarning("Input Error", "Host, User, and Password are required.")

        tk.Button(dialog, text="Connect", command=submit).grid(row=6, column=0, columnspan=2, pady=10)

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        root.wait_window(dialog)
    else:
        create_session(host, port or 22, user, passw, name)

def create_session(host, port, user, passw, name=None):
    # Create logs directory if needed
    logs_dir = os.path.join(base_dir, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, f"{host}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    # Create tab frame
    frame = ttk.Frame(session_notebook)

    # Scrollbar and output text area
    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side='right', fill='y')
    output_text = tk.Text(frame, wrap='char', yscrollcommand=scrollbar.set)
    output_text.pack(fill='both', expand=True)
    scrollbar.config(command=output_text.yview)

    # Input and buttons frame
    input_frame = tk.Frame(frame)
    input_frame.pack(fill='x')

    # Command input box full width
    entry = tk.Entry(input_frame)
    entry.pack(fill='x', expand=True)
    entry.bind('<Return>', lambda e: send_command(entry, frame))  # Enter key sends command
    entry.bind('<Up>', lambda e: history_up(entry, frame))
    entry.bind('<Down>', lambda e: history_down(entry, frame))

    # Buttons frame below entry
    buttons_frame = tk.Frame(input_frame)
    buttons_frame.pack(fill='x')

    def send_command(ent, frm):
        cmd = ent.get()
        if not cmd:
            return
        session = sessions[frm]
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        output_text.insert(tk.END, f"[{timestamp}] Sent: {cmd}\n")
        output_text.see(tk.END)
        session.send(cmd)  # Reconnect if needed and send
        # Add to history
        hist = histories[frm]
        hist['list'].append(cmd)
        hist['index'] = len(hist['list'])
        ent.delete(0, tk.END)

    # Send button
    send_btn = tk.Button(buttons_frame, text="Send", command=lambda: send_command(entry, frame))
    send_btn.pack(side='left')

    # Interrupt (Ctrl+C) button
    interrupt_btn = tk.Button(buttons_frame, text="Interrupt (Ctrl+C)", bg=themes[current_theme]['interrupt_bg'], fg=themes[current_theme]['interrupt_fg'],
                              command=lambda: sessions[frame].interrupt())
    interrupt_btn.pack(side='left')

    # Clear output button
    clear_btn = tk.Button(buttons_frame, text="Clear Output", command=lambda: output_text.delete('1.0', tk.END))
    clear_btn.pack(side='left')

    # Manual save log button
    save_btn = tk.Button(buttons_frame, text="Save Log", command=lambda: save_log(output_text))
    save_btn.pack(side='left')

    def save_log(text_widget):
        file = filedialog.asksaveasfilename(defaultextension=".log")
        if file:
            with open(file, 'w') as f:
                f.write(text_widget.get('1.0', tk.END))

    # Close tab button
    close_btn = tk.Button(buttons_frame, text="Close", command=lambda: close_session(frame))
    close_btn.pack(side='left')

    # Set tab title
    tab_title = name if name else f"{user}@{host}:{port}"
    session_notebook.add(frame, text=tab_title)

    # Create and store session, entry, history
    try:
        session = SSHSession(host, port, user, passw, output_text, log_path)
        sessions[frame] = session
        entries[frame] = entry
        histories[frame] = {'list': [], 'index': -1}
        output_text.insert(tk.END, "Connected.\n")
    except Exception as e:
        output_text.insert(tk.END, f"Connection failed: {str(e)}\n")
    apply_theme(frame, current_theme)

def history_up(ent, frm):
    hist = histories[frm]
    if hist['index'] > 0:
        hist['index'] -= 1
        ent.delete(0, tk.END)
        ent.insert(0, hist['list'][hist['index']])

def history_down(ent, frm):
    hist = histories[frm]
    if hist['index'] < len(hist['list']) - 1:
        hist['index'] += 1
        ent.delete(0, tk.END)
        ent.insert(0, hist['list'][hist['index']])
    elif hist['index'] == len(hist['list']) - 1:
        hist['index'] += 1
        ent.delete(0, tk.END)

def close_session(frame):
    # Close session and remove tab
    session = sessions.pop(frame, None)
    entries.pop(frame, None)
    histories.pop(frame, None)
    if session:
        session.close()
    session_notebook.forget(frame)

def save_current_connection():
    current_tab = session_notebook.select()
    if not current_tab:
        messagebox.showwarning("No Session", "No active session to save.")
        return
    frame = root.nametowidget(current_tab)
    session = sessions.get(frame)
    if not session:
        return
    name = simpledialog.askstring("Save Connection", "Enter a name for this connection:")
    if not name:
        return
    conn = {"name": name, "host": session.host, "port": session.port, "user": session.user, "password": session.passw}
    if conn not in saved_connections:
        saved_connections.append(conn)
        with open(connections_path, 'w') as f:
            json.dump(saved_connections, f)
        messagebox.showinfo("Saved", "Connection saved.")
    else:
        messagebox.showinfo("Already Saved", "Connection already saved.")

def connect_to_saved():
    if not saved_connections:
        messagebox.showwarning("No Saved", "No saved connections.")
        return
    dialog = tk.Toplevel(root)
    dialog.title("Connect to Saved")
    dialog.grab_set()
    apply_theme(dialog, current_theme)
    tk.Label(dialog, text="Select Connection:").pack(padx=10, pady=5)
    choices = [c.get('name', f"{c['user']}@{c['host']}:{c.get('port', 22)}") for c in saved_connections]
    combobox = ttk.Combobox(dialog, values=choices, state="readonly")
    combobox.pack(padx=10, pady=5)
    combobox.current(0)
    def connect():
        idx = combobox.current()
        if idx != -1:
            conn = saved_connections[idx]
            dialog.destroy()
            create_session(conn['host'], conn.get('port', 22), conn['user'], conn['password'], conn.get('name'))
    tk.Button(dialog, text="Connect", command=connect).pack(pady=10)
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    root.wait_window(dialog)

def manage_saved_connections():
    if not saved_connections:
        messagebox.showwarning("No Saved", "No saved connections to manage.")
        return
    manage_win = tk.Toplevel(root)
    manage_win.title("Manage Saved Connections")
    manage_win.geometry("400x300")
    apply_theme(manage_win, current_theme)

    listbox = tk.Listbox(manage_win)
    listbox.pack(fill='both', expand=True)
    def refresh_list():
        listbox.delete(0, tk.END)
        for conn in saved_connections:
            display = conn.get('name', f"{conn['user']}@{conn['host']}:{conn.get('port', 22)}")
            listbox.insert(tk.END, display)
    refresh_list()

    btn_frame = tk.Frame(manage_win)
    btn_frame.pack(fill='x')

    def edit_selected():
        selected = listbox.curselection()
        if selected:
            idx = selected[0]
            conn = saved_connections[idx]
            # Open edit dialog
            dialog = tk.Toplevel(manage_win)
            dialog.title("Edit Connection")
            dialog.grab_set()
            apply_theme(dialog, current_theme)

            tk.Label(dialog, text="Host:").grid(row=0, column=0, padx=5, pady=5)
            host_entry = tk.Entry(dialog)
            host_entry.grid(row=0, column=1, padx=5, pady=5)
            host_entry.insert(0, conn['host'])

            tk.Label(dialog, text="Port:").grid(row=1, column=0, padx=5, pady=5)
            port_entry = tk.Entry(dialog)
            port_entry.grid(row=1, column=1, padx=5, pady=5)
            port_entry.insert(0, str(conn.get('port', 22)))

            tk.Label(dialog, text="User:").grid(row=2, column=0, padx=5, pady=5)
            user_entry = tk.Entry(dialog)
            user_entry.grid(row=2, column=1, padx=5, pady=5)
            user_entry.insert(0, conn['user'])

            tk.Label(dialog, text="Name:").grid(row=3, column=0, padx=5, pady=5)
            name_entry = tk.Entry(dialog)
            name_entry.grid(row=3, column=1, padx=5, pady=5)
            name_entry.insert(0, conn.get('name', ''))

            tk.Label(dialog, text="Password:").grid(row=4, column=0, padx=5, pady=5)
            passw_entry = tk.Entry(dialog, show='*')
            passw_entry.grid(row=4, column=1, padx=5, pady=5)
            passw_entry.insert(0, conn['password'])

            def save_edit():
                saved_connections[idx]['host'] = host_entry.get()
                saved_connections[idx]['port'] = int(port_entry.get())
                saved_connections[idx]['user'] = user_entry.get()
                saved_connections[idx]['name'] = name_entry.get()
                saved_connections[idx]['password'] = passw_entry.get()
                with open(connections_path, 'w') as f:
                    json.dump(saved_connections, f)
                refresh_list()
                dialog.destroy()

            tk.Button(dialog, text="Save", command=save_edit).grid(row=5, column=0, columnspan=2, pady=10)
            dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

    tk.Button(btn_frame, text="Edit Selected", command=edit_selected).pack(side='left')

    def copy_selected():
        selected = listbox.curselection()
        if selected:
            idx = selected[0]
            conn = saved_connections[idx].copy()
            # Open edit dialog for copy
            dialog = tk.Toplevel(manage_win)
            dialog.title("Copy Connection")
            dialog.grab_set()
            apply_theme(dialog, current_theme)

            tk.Label(dialog, text="Host:").grid(row=0, column=0, padx=5, pady=5)
            host_entry = tk.Entry(dialog)
            host_entry.grid(row=0, column=1, padx=5, pady=5)
            host_entry.insert(0, conn['host'])

            tk.Label(dialog, text="Port:").grid(row=1, column=0, padx=5, pady=5)
            port_entry = tk.Entry(dialog)
            port_entry.grid(row=1, column=1, padx=5, pady=5)
            port_entry.insert(0, str(conn.get('port', 22)))

            tk.Label(dialog, text="User:").grid(row=2, column=0, padx=5, pady=5)
            user_entry = tk.Entry(dialog)
            user_entry.grid(row=2, column=1, padx=5, pady=5)
            user_entry.insert(0, conn['user'])

            tk.Label(dialog, text="Name:").grid(row=3, column=0, padx=5, pady=5)
            name_entry = tk.Entry(dialog)
            name_entry.grid(row=3, column=1, padx=5, pady=5)
            name_entry.insert(0, conn.get('name', '') + " (copy)")

            tk.Label(dialog, text="Password:").grid(row=4, column=0, padx=5, pady=5)
            passw_entry = tk.Entry(dialog, show='*')
            passw_entry.grid(row=4, column=1, padx=5, pady=5)
            passw_entry.insert(0, conn['password'])

            def save_copy():
                new_conn = {
                    'host': host_entry.get(),
                    'port': int(port_entry.get()),
                    'user': user_entry.get(),
                    'name': name_entry.get(),
                    'password': passw_entry.get()
                }
                saved_connections.append(new_conn)
                with open(connections_path, 'w') as f:
                    json.dump(saved_connections, f)
                refresh_list()
                dialog.destroy()

            tk.Button(dialog, text="Save Copy", command=save_copy).grid(row=5, column=0, columnspan=2, pady=10)
            dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

    tk.Button(btn_frame, text="Copy Selected", command=copy_selected).pack(side='left')

    def delete_selected():
        selected = listbox.curselection()
        if selected:
            idx = selected[0]
            del saved_connections[idx]
            with open(connections_path, 'w') as f:
                json.dump(saved_connections, f)
            refresh_list()
            messagebox.showinfo("Deleted", "Connection deleted.")

    tk.Button(btn_frame, text="Delete Selected", command=delete_selected).pack(side='left')

    def move_up():
        selected = listbox.curselection()
        if selected:
            idx = selected[0]
            if idx > 0:
                saved_connections.insert(idx - 1, saved_connections.pop(idx))
                with open(connections_path, 'w') as f:
                    json.dump(saved_connections, f)
                refresh_list()
                listbox.selection_set(idx - 1)

    tk.Button(btn_frame, text="Move Up", command=move_up).pack(side='left')

    def move_down():
        selected = listbox.curselection()
        if selected:
            idx = selected[0]
            if idx < len(saved_connections) - 1:
                saved_connections.insert(idx + 1, saved_connections.pop(idx))
                with open(connections_path, 'w') as f:
                    json.dump(saved_connections, f)
                refresh_list()
                listbox.selection_set(idx + 1)

    tk.Button(btn_frame, text="Move Down", command=move_down).pack(side='left')

def open_settings():
    settings_win = tk.Toplevel(root)
    settings_win.title("Settings - Manage Commands")
    settings_win.geometry("600x400")
    apply_theme(settings_win, current_theme)

    # Treeview for categories and commands
    tree = ttk.Treeview(settings_win, columns=('Command',), show='tree headings')
    tree.heading('#0', text='Tab/Button')
    tree.heading('Command', text='Command')
    tree.pack(fill='both', expand=True)

    # Populate tree
    def populate_tree():
        # Preserve expanded categories
        open_cats = [tree.item(iid)['text'] for iid in tree.get_children() if tree.item(iid, 'open')]
        tree.delete(*tree.get_children())
        for cat in commands:
            cat_id = tree.insert('', 'end', text=cat)
            for name, cmd in commands[cat].get('commands', {}).items():
                tree.insert(cat_id, 'end', text=name, values=(cmd,))
        # Re-expand previously open categories
        for cat_id in tree.get_children():
            if tree.item(cat_id)['text'] in open_cats:
                tree.item(cat_id, open=True)

    populate_tree()

    # Buttons frame
    btn_frame = tk.Frame(settings_win)
    btn_frame.pack(fill='x')

    def add_category():
        cat_name = simpledialog.askstring("Add Category", "Enter category name:")
        if cat_name and cat_name not in commands:
            commands[cat_name] = {'commands': {}, 'reference': {'text': '', 'images': []}}
            save_commands()
            populate_tree()

    tk.Button(btn_frame, text="Add Category", command=add_category).pack(side='left')

    def delete_selected():
        selected = tree.selection()
        if selected:
            item = selected[0]
            parent = tree.parent(item)
            if parent:  # It's a command
                cat = tree.item(parent)['text']
                name = tree.item(item)['text']
                del commands[cat]['commands'][name]
            else:  # It's a category
                cat = tree.item(item)['text']
                del commands[cat]
            save_commands()
            populate_tree()

    tk.Button(btn_frame, text="Delete Selected", command=delete_selected).pack(side='left')

    def edit_selected():
        selected = tree.selection()
        if selected:
            item = selected[0]
            parent = tree.parent(item)
            if parent:  # Command
                cat = tree.item(parent)['text']
                old_name = tree.item(item)['text']
                new_name = simpledialog.askstring("Edit Name", "New button name:", initialvalue=old_name)
                new_cmd = simpledialog.askstring("Edit Command", "New command:", initialvalue=tree.item(item)['values'][0])
                if new_name and new_cmd:
                    del commands[cat]['commands'][old_name]
                    commands[cat]['commands'][new_name] = new_cmd
            else:  # Category
                cat = tree.item(item)['text']
                new_cat = simpledialog.askstring("Edit Category", "New category name:", initialvalue=cat)
                if new_cat:
                    commands[new_cat] = commands.pop(cat)
            save_commands()
            populate_tree()

    tk.Button(btn_frame, text="Edit Selected", command=edit_selected).pack(side='left')

    def add_command():
        selected = tree.selection()
        if selected:
            item = selected[0]
            if not tree.parent(item):  # Category selected
                cat = tree.item(item)['text']
                name = simpledialog.askstring("Add Command", "Button name:")
                cmd = simpledialog.askstring("Add Command", "Command:")
                if name and cmd:
                    commands[cat]['commands'][name] = cmd
                    save_commands()
                    populate_tree()

    tk.Button(btn_frame, text="Add Command to Selected Category", command=add_command).pack(side='left')

    def edit_reference():
        selected = tree.selection()
        if selected:
            item = selected[0]
            if not tree.parent(item):  # Category selected
                cat = tree.item(item)['text']
                ref = commands[cat].setdefault('reference', {'text': '', 'images': []})
                # Single window for edit
                ref_win = tk.Toplevel(settings_win)
                ref_win.title("Edit Reference for " + cat)
                apply_theme(ref_win, current_theme)
                # Text
                tk.Label(ref_win, text="Reference Text (use **bold**, *italic*):").pack(anchor='w')
                text_entry = Text(ref_win, wrap='word', height=10)
                text_entry.pack(fill='both', expand=True)
                text_entry.insert('1.0', ref['text'])
                # Images
                tk.Label(ref_win, text="Images (added at bottom):").pack(anchor='w')
                images_list = tk.Listbox(ref_win)
                images_list.pack(fill='both', expand=True)
                for img in ref['images']:
                    images_list.insert(tk.END, img)
                def add_image():
                    file = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif")])
                    if file:
                        # Copy to images dir
                        img_dir = os.path.join(base_dir, 'images')
                        os.makedirs(img_dir, exist_ok=True)
                        dest_path = os.path.join(img_dir, os.path.basename(file))
                        if os.path.exists(dest_path):
                            base, ext = os.path.splitext(os.path.basename(file))
                            counter = 1
                            while os.path.exists(dest_path):
                                dest_path = os.path.join(img_dir, f"{base}_{counter}{ext}")
                                counter += 1
                        shutil.copy(file, dest_path)
                        ref['images'].append(dest_path)
                        images_list.insert(tk.END, dest_path)
                        save_commands()
                def delete_image():
                    selected = images_list.curselection()
                    if selected:
                        idx = selected[0]
                        del ref['images'][idx]
                        images_list.delete(idx)
                        save_commands()
                btn_frame_img = tk.Frame(ref_win)
                btn_frame_img.pack(fill='x')
                tk.Button(btn_frame_img, text="Add Image", command=add_image).pack(side='left')
                tk.Button(btn_frame_img, text="Delete Selected Image", command=delete_image).pack(side='left')
                def save_text():
                    ref['text'] = text_entry.get('1.0', tk.END).strip()
                    save_commands()
                    ref_win.destroy()
                tk.Button(ref_win, text="Save Reference", command=save_text).pack()

    tk.Button(btn_frame, text="Edit Reference for Category", command=edit_reference).pack(side='left')

    # Reorder buttons (up/down for categories and commands)
    def move_up():
        selected = tree.selection()
        if selected:
            item = selected[0]
            parent = tree.parent(item)
            index = tree.index(item)
            if index > 0:
                if parent:
                    # Move command up in category
                    cat = tree.item(parent)['text']
                    keys = list(commands[cat]['commands'].keys())
                    keys.insert(index - 1, keys.pop(index))
                    new_dict = {k: commands[cat]['commands'][k] for k in keys}
                    commands[cat]['commands'] = new_dict
                else:
                    # Move category up
                    keys = list(commands.keys())
                    keys.insert(index - 1, keys.pop(index))
                    new_dict = {k: commands[k] for k in keys}
                    commands.clear()
                    commands.update(new_dict)
                save_commands()
                populate_tree()
                tree.selection_set(item)  # Keep selected

    tk.Button(btn_frame, text="Move Up", command=move_up).pack(side='left')

    def move_down():
        selected = tree.selection()
        if selected:
            item = selected[0]
            parent = tree.parent(item)
            index = tree.index(item)
            if parent:
                if index < len(tree.get_children(parent)) - 1:
                    cat = tree.item(parent)['text']
                    keys = list(commands[cat]['commands'].keys())
                    keys.insert(index + 1, keys.pop(index))
                    new_dict = {k: commands[cat]['commands'][k] for k in keys}
                    commands[cat]['commands'] = new_dict
            else:
                if index < len(tree.get_children()) - 1:
                    keys = list(commands.keys())
                    keys.insert(index + 1, keys.pop(index))
                    new_dict = {k: commands[k] for k in keys}
                    commands.clear()
                    commands.update(new_dict)
            save_commands()
            populate_tree()
            tree.selection_set(item)  # Keep selected

    tk.Button(btn_frame, text="Move Down", command=move_down).pack(side='left')

def save_commands():
    with open(commands_path, 'w') as f:
        json.dump(commands, f)
    rebuild_commands_notebook()

def export_commands():
    file = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
    if file:
        with open(file, 'w') as f:
            json.dump(commands, f)
        messagebox.showinfo("Exported", "Commands exported successfully.")

def import_commands():
    file = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if file:
        with open(file, 'r') as f:
            global commands
            commands = json.load(f)
        save_commands()
        messagebox.showinfo("Imported", "Commands imported successfully.")

# Menu bar
menu = tk.Menu(root)
root.config(menu=menu)
file_menu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="New Connection", command=add_new_session)
file_menu.add_command(label="Connect to Saved", command=connect_to_saved)
file_menu.add_command(label="Save Current Connection", command=save_current_connection)
file_menu.add_command(label="Export Commands", command=export_commands)
file_menu.add_command(label="Import Commands", command=import_commands)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)

settings_menu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="Settings", menu=settings_menu)
settings_menu.add_command(label="Manage Commands", command=open_settings)
settings_menu.add_command(label="Manage Saved Connections", command=manage_saved_connections)

# Apply initial theme
apply_theme(root, current_theme)

# Start the GUI loop
root.mainloop()
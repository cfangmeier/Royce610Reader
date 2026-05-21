import re
import sys
import serial
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

MOCK = False

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class MockSerial:

    BREAK_TYPES = [
        "NECK BREAK        ",
        "SPAN BREAK        ",
        "DIE INT BRK       ",
        "SUB INT BRK       ",
        "DIE MT LIFT       ",
        "SUB MT LIFT       ",
        "DIE FRACT         ",
        "SUB FRACT         ",
        "FAIL TEXT 9       ",
        "OPERATOR VOID     ",
        "TEST CANCELLED    ",
        "OVERTRAVEL        ",
        "NO CODE ASSIGNED  "
    ]

    def __init__(self):
        self.mean = 10
        self.std = 3
        self.codes = list(range(13))
        self.idx = 1

    def readline(self):
        from random import random, gammavariate, choice
        if random() < 0.80:
            return None
        mode_idx = choice(range(len(self.BREAK_TYPES)))
        line = f"{self.idx: 5d},{gammavariate(self.mean**2/self.std**2, self.mean/self.std**2): 8.1f},"\
               f"\"{self.BREAK_TYPES[mode_idx]:s}\",{mode_idx+1: 5d}"
        self.idx += 1
        return line

    def close(self):
        pass


class Monitor:
    REX = re.compile(r" *(\d+), *([0-9.]+) *,\"([A-Z0-9- ]+[A-Z0-9]) *\", *(\d+) *")

    def __init__(self, port: serial.Serial):
        self.port = port
        self._stop = False

    @staticmethod
    def get_ports():
        if MOCK:
            ports = ["COM1", "COM2", "COM3"]
        else:
            from serial.tools import list_ports
            ports = [port.name for port in list_ports.comports()]
        print(f"Available COM ports: {ports}")
        return ports

    def check(self):
        line = self.port.readline()
        if line:
            if type(line) is bytes:
                line = bytes([byte & 0x7F for byte in line]).decode('ascii')
            line = line.strip()
            print(line)
            match = self.REX.match(line)
            if match is None:
                print("Failed to parse line, proceeding to next")
                return None
            return match.groups()
        return None


class UI:
    def __init__(self):
        self.monitor = None
        self.current_port_name = None
        self.results = []
        self.shortcuts = self.load_config()

        self.root = tk.Tk()
        self.root.geometry("1200x950")
        self.root.wm_title("Royce 610 Pull-tester Interface")
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Menu bar
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)

        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=self.file_menu)

        self.port_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label="Open Port", menu=self.port_menu)
        self.update_port_menu()

        self.file_menu.add_command(label="Load CSV", command=self.load_csv)
        self.file_menu.add_command(label="Save CSV", command=self.save_csv)
        self.file_menu.add_command(label="Save Plot", command=self.save_plot)
        self.file_menu.add_command(label="Clear Data", command=self.clear_data)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Quit", command=self.quit)

        self.menubar.add_command(label="Config", command=self.open_config)

        left_frame = ttk.Frame(self.root, padding=10)
        left_frame.grid(column=0, row=0, sticky=tk.NSEW)

        table_frame = tk.Frame(left_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)
        table_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        table_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.table = ttk.Treeview(table_frame, column=("c1", "c2", "c3", "c4"), show='headings', height=30,
                                  yscrollcommand=table_scroll.set)
        self.table.column("# 1", anchor=tk.CENTER, width=110)
        self.table.heading("# 1", text="Bond ID")
        self.table.column("# 2", anchor=tk.CENTER, width=135)
        self.table.heading("# 2", text="Break Strength")
        self.table.column("# 3", anchor=tk.CENTER, width=185)
        self.table.heading("# 3", text="Failure Mode")
        self.table.column("# 4", anchor=tk.CENTER, width=85)
        self.table.heading("# 4", text="Broken Bond")

        self.table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        table_scroll.config(command=self.table.yview)
        self.add_dummy_rows()

        right_frame = ttk.Frame(self.root, padding=10)
        right_frame.grid(column=1, row=0, sticky=tk.NSEW)

        break_type_frame = ttk.LabelFrame(right_frame, text="Break Types")
        break_type_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 10))
        self.break_counts = {}

        self.img_foot_lift = tk.PhotoImage(file=resource_path("resources/Wire-foot-lift.png"))
        self.img_heel_break = tk.PhotoImage(file=resource_path("resources/Wire-heel-break.png"))

        break_type_frame.columnconfigure(0, weight=1)
        break_type_frame.columnconfigure(1, weight=1)
        break_type_frame.rowconfigure(0, weight=1)
        break_type_frame.rowconfigure(1, weight=1)

        btn_foot_lift = tk.Button(break_type_frame, image=self.img_foot_lift, command=self.set_fl)
        btn_foot_lift.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        btn_heel_break = tk.Button(break_type_frame, image=self.img_heel_break, command=self.set_hb)
        btn_heel_break.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)

        btn_bond1 = tk.Button(break_type_frame, text="Bond 1", font=("Arial", 12, "bold"), command=lambda: self.set_bond(1))
        btn_bond1.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        btn_bond2 = tk.Button(break_type_frame, text="Bond 2", font=("Arial", 12, "bold"), command=lambda: self.set_bond(2))
        btn_bond2.grid(row=1, column=1, sticky="nsew", padx=2, pady=2)

        self.fig = Figure(figsize=(7, 5), dpi=80)
        self.ax: Axes = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, master=right_frame)
        self.update_plot()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.bind_shortcuts()

        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky=tk.EW)
        self.update_status_bar()

        last_port = self.shortcuts.get("last_port")
        if last_port:
            self.root.after(100, lambda: self.auto_connect(last_port))

    def update_port_menu(self):
        self.port_menu.delete(0, tk.END)
        ports = Monitor.get_ports()
        for p in ports:
            label = f"✓ {p}" if p == self.current_port_name else p
            self.port_menu.add_command(label=label, command=lambda port=p: self.start_monitor(port))
        self.port_menu.add_separator()
        self.port_menu.add_command(label="Refresh", command=self.update_port_menu)
        
        state = tk.NORMAL if self.monitor else tk.DISABLED
        self.port_menu.add_command(label="Disconnect", command=self.disconnect, state=state)

    def disconnect(self):
        if self.monitor:
            self.monitor.port.close()
            self.monitor = None
        self.current_port_name = None
        self.update_port_menu()
        self.update_status_bar()

    def start_monitor(self, port_name):
        was_running = self.monitor is not None
        if was_running:
            self.monitor.port.close()
            self.monitor = None
            self.current_port_name = None

        if MOCK:
            port = MockSerial()
        else:
            try:
                port = serial.Serial(port_name, 9600, timeout=0.05)
            except serial.SerialException:
                messagebox.showerror("Port Error", f"Failed to Open Port {port_name}!")
                self.update_port_menu()
                return
        
        self.current_port_name = port_name
        self.monitor = Monitor(port)
        self.update_port_menu()
        self.update_status_bar()
        
        if not was_running:
            self.check_monitor()

    def check_monitor(self):
        if self.monitor:
            if result := self.monitor.check():
                self.add_result(result)
            self.root.after(100, self.check_monitor)

    def add_result(self, result):
        # result is (id, strength, mode, bond)
        # Initial data point only shows Bond ID and Strength
        new_result = [result[0], result[1], "", ""]
        self.results.append(new_result)

        # Insert before dummy rows
        item_id = self.table.insert('', len(self.results) - 1, values=new_result)
        self.table.selection_set(item_id)
        self.table.focus(item_id)
        
        # Scroll so that the end of the table (dummies) is visible
        all_items = self.table.get_children()
        if all_items:
            self.table.see(all_items[-1])

        self.update_plot()
        self.update_status_bar()

    def set_hb(self):
        selected = self.table.selection()
        if not selected:
            return
        item_id = selected[0]
        idx = self.table.index(item_id)
        if idx >= len(self.results):
            return
        self.results[idx][2] = "HB"
        self.table.item(item_id, values=self.results[idx])
        self.update_status_bar()

    def set_fl(self):
        selected = self.table.selection()
        if not selected:
            return
        item_id = selected[0]
        idx = self.table.index(item_id)
        if idx >= len(self.results):
            return
        self.results[idx][2] = "FL"
        self.table.item(item_id, values=self.results[idx])
        self.update_status_bar()

    def set_bond(self, bond):
        selected = self.table.selection()
        if not selected:
            return
        item_id = selected[0]
        idx = self.table.index(item_id)
        if idx >= len(self.results):
            return
        self.results[idx][3] = str(bond)
        self.table.item(item_id, values=self.results[idx])
        self.update_status_bar()

    def update_plot(self):
        from statistics import mean, stdev
        self.ax.clear()
        strengths = [float(res[1]) for res in self.results]
        self.ax.hist(strengths, bins=range(20), rwidth=0.95, color='red')
        self.ax.set_xlabel('Break Strength (gf)')
        # self.ax.grid()
        self.ax.set_xticks(list(range(21)), minor=True)
        self.ax.set_xticks([0, 5, 10, 15, 20], minor=False)

        if len(strengths) > 2:
            text = (
                f"$\\mu={mean(strengths):.1f}$ gf\n"
                f"$\\sigma={stdev(strengths):.1f}$ gf\n"
                f"$N={len(strengths):3d}$"
            )
        else:
            text = (
                "$\\mu=\\mathrm{N/A}$\n"
                "$\\sigma=\\mathrm{N/A}$\n"
                f"$N={len(strengths):3d}$"
            )

        self.ax.text(0.01, 0.97, text, transform=self.fig.transFigure,
                     horizontalalignment="left", verticalalignment="top",
                     bbox=dict(facecolor='white', alpha=0.9, linewidth=2.0))

        self.canvas.draw()

    def load_csv(self):
        filename = filedialog.askopenfilename(title="Select CSV file to load",
                                              filetypes=(('CSV Files', '*.csv'), ('All Files', '*.*')))
        if not filename:
            return

        try:
            with open(filename, 'r') as f:
                loaded_count = 0
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(',')
                    if len(parts) >= 2:
                        # Format: Bond ID, Strength, Mode, Bond
                        bond_id = parts[0]
                        strength = parts[1]
                        mode = parts[2] if len(parts) > 2 else ""
                        bond = parts[3] if len(parts) > 3 else ""

                        new_item = [bond_id, strength, mode, bond]
                        self.results.append(new_item)

                        # Insert before dummy rows
                        self.table.insert('', len(self.results) - 1, values=new_item)
                        loaded_count += 1

            if loaded_count > 0:
                self.update_plot()
                self.update_status_bar()
                # Scroll to show the newly added items (towards the bottom)
                all_items = self.table.get_children()
                if all_items:
                    self.table.see(all_items[-1])

        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load CSV: {e}")

    def save_csv(self):
        filename = filedialog.asksaveasfilename(title="Please specify output filename.", defaultextension="csv",
                                                filetypes=(('CSV Files', '*.csv'),))
        if not filename:
            return False
        print(f"Saving results to: \"{filename}\"")
        try:
            with open(filename, 'w') as f:
                for result in self.results:
                    f.write(f"{result[0]},{result[1]},{result[2]},{result[3]}\n")
            return True
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save CSV: {e}")
            return False

    def save_plot(self):
        filename = filedialog.asksaveasfilename(title="Save Plot As", defaultextension=".png",
                                                filetypes=(('PNG Files', '*.png'), ('All Files', '*.*')))
        if not filename:
            return
        print(f"Saving plot to: \"{filename}\"")
        self.fig.savefig(filename)

    def clear_data(self):
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all current data?"):
            self.results = []
            self.table.delete(*self.table.get_children())
            self.add_dummy_rows()
            self.update_plot()
            self.update_status_bar()

    def add_dummy_rows(self):
        for _ in range(2):
            self.table.insert('', 'end', values=("", "", "", ""))

    def update_status_bar(self):
        port = self.current_port_name if self.current_port_name else "Disconnected"
        fl = sum(1 for r in self.results if r[2] == "FL")
        hb = sum(1 for r in self.results if r[2] == "HB")
        b1 = sum(1 for r in self.results if r[3] == "1")
        b2 = sum(1 for r in self.results if r[3] == "2")
        self.status_var.set(f"{port} | FL/HB: {fl}/{hb} | Bond 1/2: {b1}/{b2}")

    def run(self):
        self.root.mainloop()

    def quit(self):
        if self.results:
            ans = messagebox.askyesnocancel("Save Before Exit?", "You have unsaved data. Would you like to save it before exiting?")
            if ans is True: # Yes
                if not self.save_csv():
                    return # User cancelled save dialog or error occurred, abort quit
            elif ans is None: # Cancel
                return
            # if False (No), proceed to quit

        if self.monitor:
            self.monitor.port.close()
            self.monitor = None
        
        # Save current port to config for auto-connect
        self.shortcuts["last_port"] = self.current_port_name
        self.save_config(self.shortcuts)
        
        self.root.destroy()

    def auto_connect(self, port_name):
        self.start_monitor(port_name)
        if self.monitor is None:
            # Failed to connect (start_monitor showed error)
            # Clear it from config so we don't try again next time unless manually opened
            self.shortcuts["last_port"] = None
            self.save_config(self.shortcuts)

    def get_config_path(self):
        appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        config_dir = os.path.join(appdata, 'Royce610Reader')
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, 'config.json')

    def load_config(self):
        self.config_path = self.get_config_path()
        defaults = {
            "bond1": "1",
            "bond2": "2",
            "foot_lift": "q",
            "heel_break": "w",
            "last_port": None
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    defaults.update(config)
            except Exception as e:
                print(f"Error loading config: {e}")
        return defaults

    def save_config(self, config):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save configuration: {e}")

    def bind_shortcuts(self):
        if not hasattr(self, '_bound_ids'):
            self._bound_ids = []

        # Unbind all previous
        for char, func_id in self._bound_ids:
            try:
                self.root.unbind(char, func_id)
            except:
                pass
        self._bound_ids = []

        def wrap(func):
            def wrapper(event):
                # Don't trigger if an Entry widget has focus
                if isinstance(self.root.focus_get(), tk.Entry):
                    return
                func()
            return wrapper

        mappings = [
            (self.shortcuts['bond1'], wrap(lambda: self.set_bond(1))),
            (self.shortcuts['bond2'], wrap(lambda: self.set_bond(2))),
            (self.shortcuts['foot_lift'], wrap(lambda: self.set_fl())),
            (self.shortcuts['heel_break'], wrap(lambda: self.set_hb())),
        ]

        for char, func in mappings:
            try:
                # Use the char directly for simple alphanumeric keys
                fid = self.root.bind(char, func)
                self._bound_ids.append((char, fid))
            except tk.TclError as e:
                print(f"Failed to bind key '{char}': {e}")

    def open_config(self):
        config_win = tk.Toplevel(self.root)
        config_win.title("Keyboard Shortcuts Configuration")
        config_win.geometry("450x300")
        config_win.grab_set()

        temp_shortcuts = dict(self.shortcuts)
        
        fields = [
            ("bond1", "Bond 1 Key"),
            ("bond2", "Bond 2 Key"),
            ("foot_lift", "Foot Lift Key"),
            ("heel_break", "Heel Break Key")
        ]

        buttons = []
        labels = {}

        def start_listening(key_id, val_label, current_btn):
            # Disable all interaction during listening
            for b in buttons:
                b.config(state=tk.DISABLED)
            
            current_btn.config(text="Press a key...", state=tk.DISABLED)
            config_win.focus_set()

            def on_key(event):
                config_win.unbind("<Key>")
                # Re-enable buttons
                for b in buttons:
                    b.config(state=tk.NORMAL)
                current_btn.config(text="Set shortcut")
                
                if event.keysym == "Escape":
                    return
                
                new_key = event.keysym
                
                # Check for duplicates
                if any(v == new_key for k, v in temp_shortcuts.items() if k != key_id):
                    messagebox.showerror("Duplicate Key", f"The key '{new_key}' is already assigned to another action.")
                    return

                temp_shortcuts[key_id] = new_key
                val_label.config(text=new_key)

            config_win.bind("<Key>", on_key)

        for i, (key, label_text) in enumerate(fields):
            tk.Label(config_win, text=label_text).grid(row=i, column=0, padx=10, pady=10, sticky="e")
            
            val_label = tk.Label(config_win, text=temp_shortcuts[key], font=("Arial", 10, "bold"), width=15, relief="sunken", anchor="center")
            val_label.grid(row=i, column=1, padx=10, pady=10)
            labels[key] = val_label
            
            btn = tk.Button(config_win, text="Set shortcut", width=12)
            btn.grid(row=i, column=2, padx=10, pady=10)
            btn.config(command=lambda k=key, l=val_label, b=btn: start_listening(k, l, b))
            buttons.append(btn)

        def save():
            self.shortcuts = temp_shortcuts
            self.save_config(self.shortcuts)
            self.bind_shortcuts()
            config_win.destroy()
            messagebox.showinfo("Success", "Configuration saved and applied.")

        save_btn = tk.Button(config_win, text="Save", command=save, width=15)
        save_btn.grid(row=len(fields), column=0, columnspan=3, pady=20)
        buttons.append(save_btn)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser('Royce610Reader')
    parser.add_argument('-m', action="store_true",
                        help="Mock the serial communication for offline development.")
    args = parser.parse_args()
    MOCK = args.m
    ui = UI()
    ui.run()


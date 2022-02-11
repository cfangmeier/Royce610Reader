import re
import serial
import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

MOCK = False

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


class MockSerial:

    def __init__(self):
        self.mean = 10
        self.std = 3
        self.codes = list(range(13))
        self.idx = 1

    def readline(self):
        from random import random, gammavariate, choice
        if random() < 0.80:
            return None
        mode_idx = choice(range(len(BREAK_TYPES)))
        line = f"{self.idx: 5d},{gammavariate(self.mean**2/self.std**2, self.mean/self.std**2): 8.1f},"\
               f"\"{BREAK_TYPES[mode_idx]:s}\",{mode_idx+1: 5d}"
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
        from serial.tools import list_ports
        if MOCK:
            ports = ["COM1", "COM2", "COM3"]
        else:
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


class UI:
    def __init__(self):
        self.monitor = None
        self.results = []

        self.root = tk.Tk()
        self.root.geometry("780x760")
        self.root.wm_title("Royce 610 Pull-tester Interface")
        left_frame = ttk.Frame(self.root, padding=10)
        left_frame.grid(column=0, row=0, sticky=tk.NW)

        table_frame = tk.Frame(left_frame)
        table_frame.grid(column=0, row=0)
        table_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        table_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.table = ttk.Treeview(table_frame, column=("c1", "c2", "c3", "c4"), show='headings', height=15,
                                  yscrollcommand=table_scroll.set)
        self.table.column("# 1", anchor=tk.CENTER, width=110)
        self.table.heading("# 1", text="Bond ID")
        self.table.column("# 2", anchor=tk.CENTER, width=135)
        self.table.heading("# 2", text="Break Strength")
        self.table.column("# 3", anchor=tk.CENTER, width=185)
        self.table.heading("# 3", text="Failure Mode")
        self.table.column("# 4", anchor=tk.CENTER, width=85)
        self.table.heading("# 4", text="Code")

        self.table.pack(side=tk.LEFT, fill=tk.BOTH)
        table_scroll.config(command=self.table.yview)

        ttk.Separator(left_frame, orient='horizontal').grid(column=0, row=1, sticky='ew', pady=10)

        self.fig = Figure(figsize=(7, 5), dpi=80)
        self.ax: Axes = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, master=left_frame)
        self.update_plot()
        self.canvas.get_tk_widget().grid(column=0, row=2, sticky=tk.S)

        right_frame = ttk.Frame(self.root, padding=10)
        right_frame.grid(column=1, row=0, sticky=tk.NE)

        control_frame = ttk.Frame(right_frame, borderwidth=5, relief='sunken')
        control_frame.pack(side=tk.TOP)

        monitor_frame = ttk.Frame(control_frame)
        ttk.Label(monitor_frame, text="Select COM Port").pack(side=tk.TOP)
        ports = Monitor.get_ports()
        self.port_select = tk.StringVar()
        if ports:
            self.port_select.set(ports[0])
        ttk.OptionMenu(monitor_frame, self.port_select, "", *ports).pack(side=tk.LEFT)
        ttk.Button(monitor_frame, text="Connect", command=self.start_monitor).pack(side=tk.RIGHT)
        ttk.Separator(monitor_frame, orient='horizontal').pack(side=tk.BOTTOM, fill='x')
        monitor_frame.pack(side=tk.TOP, expand=True)

        bottom_right_frame = ttk.Frame(right_frame)
        bottom_right_frame.pack(side=tk.BOTTOM)

        ttk.Button(bottom_right_frame, text="Save CSV", command=self.save_csv).pack()
        ttk.Button(bottom_right_frame, text="Quit", command=self.quit).pack()

        break_type_frame = ttk.LabelFrame(right_frame, text="Break Types", height=500)
        break_type_frame.pack(side=tk.BOTTOM, expand=True, fill=tk.BOTH)
        self.break_counts = {}
        for idx, break_type in enumerate(BREAK_TYPES):
            bt = break_type.strip()
            ttk.Label(break_type_frame, text=bt).grid(row=idx, column=0, sticky=tk.W)
            count = ttk.Label(break_type_frame, text="0")
            count.grid(row=idx, column=1, sticky=tk.E)
            self.break_counts[bt] = count

    def start_monitor(self):
        if self.monitor:
            return
        if MOCK:
            port = MockSerial()
        else:
            try:
                port = serial.Serial(self.port_select.get(), 9600, timeout=0.05)
            except serial.SerialException:
                top = tk.Toplevel(self.root)
                top.geometry("150x50")
                top.title("Port Error")
                ttk.Label(top, text="Failed to Open Port!").place(x=10, y=10)
                return
        self.monitor = Monitor(port)
        self.check_monitor()

    def check_monitor(self):
        if self.monitor:
            if result := self.monitor.check():
                self.add_result(result)
            self.root.after(100, self.check_monitor)

    def add_result(self, result):
        self.results.append(result)
        self.table.insert('', 'end', text="5", values=result)
        self.table.yview_moveto(1)
        self.update_plot()
        self.update_counts()

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

    def update_counts(self):
        from collections import defaultdict
        counts = defaultdict(int)
        for result in self.results:
            counts[result[2]] += 1
        for type_, count in counts.items():
            try:
                self.break_counts[type_]["text"] = str(count)
            except KeyError:
                print(f"Unknown break type: {type_}")


    def save_csv(self):
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(title="Please specify output filename.", defaultextension="csv",
                                                filetypes=(('CSV Files', '*.csv'),))
        if not filename:
            return
        print(f"Saving results to: \"{filename}\"")
        with open(filename, 'w') as f:
            for result in self.results:
                f.write(f"{result[0]},{result[1]},{result[2]},{result[3]}\n")

    def run(self):
        self.root.mainloop()

    def quit(self):
        if self.monitor:
            self.monitor.port.close()
            self.monitor = None
        self.root.destroy()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser('Royce610Reader')
    parser.add_argument('-m', action="store_true",
                        help="Mock the serial communication for offline development.")
    args = parser.parse_args()
    MOCK = args.m
    ui = UI()
    ui.run()


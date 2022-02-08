import serial
import re
import typing as typ
import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

MOCK = False

# Sample lines:
#  `8,   0.7  ,"NON-DESTRUCT      ", 0`
#  `9,   0.7  ,"NON-DESTRUCT      ", 0`
#  `10,   9.7  ,"NO CODE ASSIGNED  ",13`


class MockSerial:

    def __init__(self):
        self.mean = 10
        self.std = 3
        self.modes = ['NON-DESTRUCT', 'NO CODE ASSIGNED']
        self.codes = list(range(13))
        self.idx = 0

    def readline(self):
        from time import sleep
        from random import random, gammavariate, choice
        sleep(random())
        ## @TODO: Update this to match real output
        line = f"{self.idx: 5d}{gammavariate(self.mean**2/self.std**2, self.mean/self.std**2): 8.1f}"\
               f"   {choice(self.modes):<16s}{choice(self.codes): 5d}"
        self.idx += 1
        return line

    def close(self):
        pass


class Monitor:
    REX = re.compile(r" *(\d+), *([0-9.]+) *,\"([A-Z- ]+[A-Z]) *\", *(\d+) *")

    def __init__(self, port_name: str, callback: typ.Callable):
        self.callback = callback
        self.port_name = port_name
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

    def monitor(self):
        self._stop = False
        if MOCK:
            port = MockSerial()
        else:
            port = serial.Serial(self.port_name, 9600, timeout=0.1)
        print("Port Monitor Started")
        while True:
            if self._stop:
                break
            line = port.readline()
            if line:
                if type(line) is bytes:
                    line = bytes([byte & 0x7F for byte in line]).decode('ascii')
                line = line.strip()
                print(line)
                match = self.REX.match(line)
                if match is None:
                    print("Failed to parse line, proceeding to next")
                    continue
                result = match.groups()
                if not self._stop:
                    self.callback(result)
        port.close()
        print("Port Monitor Stopped")

    def stop(self):
        self._stop = True


class UI:
    def __init__(self):
        self.monitor = None
        self.monitor_thread = None
        self.results = []

        self.root = tk.Tk()
        self.root.geometry("1000x800")
        self.root.wm_title("Royce 610 Pull-tester Interface")
        self.root.grid()
        left_frame = ttk.Frame(self.root, padding=10)
        left_frame.grid(column=0, row=0)

        left_frame.grid(pady=10)

        table_frame = tk.Frame(left_frame)
        table_frame.grid(column=0, row=0)
        table_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        table_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.table = ttk.Treeview(table_frame, column=("c1", "c2", "c3", "c4"), show='headings', height=10,
                                  yscrollcommand=table_scroll.set)
        self.table.column("# 1", anchor=tk.CENTER)
        self.table.heading("# 1", text="Bond ID")
        self.table.column("# 2", anchor=tk.CENTER)
        self.table.heading("# 2", text="Break Strength")
        self.table.column("# 3", anchor=tk.CENTER)
        self.table.heading("# 3", text="Failure Mode")
        self.table.column("# 4", anchor=tk.CENTER)
        self.table.heading("# 4", text="Code")

        self.table.pack(side=tk.LEFT, fill=tk.BOTH)
        table_scroll.config(command=self.table.yview)

        self.fig = Figure(figsize=(8, 5), dpi=100)
        self.ax: Axes = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, master=left_frame)
        self.update_plot()
        self.canvas.get_tk_widget().grid(column=0, row=2)

        right_frame = ttk.Frame(self.root, padding=10)
        right_frame.grid(column=1, row=0)

        monitor_frame = ttk.Frame(right_frame)
        ttk.Label(monitor_frame, text="Select COM Port").pack()
        ports = Monitor.get_ports()
        self.clicked = tk.StringVar()
        if ports:
            self.clicked.set(ports[0])
        self.serial_option_menu = ttk.OptionMenu(monitor_frame, self.clicked, "", *ports)
        self.serial_option_menu.pack()
        ttk.Button(monitor_frame, text="Connect", command=self.start_monitor).pack(side=tk.BOTTOM)
        monitor_frame.pack(side=tk.TOP, expand=True)

        ttk.Button(right_frame, text="Quit", command=self.quit).pack(side=tk.BOTTOM)
        ttk.Button(right_frame, text="Save CSV", command=self.save_csv).pack(side=tk.BOTTOM)

    def start_monitor(self):
        import threading
        self.monitor = Monitor(self.clicked.get(), callback=self.add_result)
        self.monitor_thread = threading.Thread(target=self.monitor.monitor)  # , daemon=True)
        self.monitor_thread.start()

    def add_result(self, result):
        self.results.append(result)
        self.table.insert('', 'end', text="5", values=result)
        self.table.yview_moveto(1)
        self.update_plot()

    def update_plot(self):
        from statistics import mean, stdev
        self.ax.clear()
        strengths = [float(res[1]) for res in self.results]
        self.ax.hist(strengths, bins=range(20))
        self.ax.set_xlabel('Break Strength (gf)')

        if len(strengths) > 2:
            text = (
                f"$\\mu={mean(strengths):.1f}$ \n"
                f"$\\sigma={stdev(strengths):.1f}$"
            )
        else:
            text = (
                "$\\mu=\\mathrm{N/A}$ \n"
                "$\\sigma=\\mathrm{N/A}$"
            )

        self.ax.text(0.01, 0.99, text, transform=self.fig.transFigure,
                     horizontalalignment="left", verticalalignment="top",
                     bbox=dict(facecolor='white', alpha=0.9, linewidth=2.0))

        self.canvas.draw()

    def save_csv(self):
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(title="Please specify output filename.", defaultextension="csv",
                                                filetypes=(('CSV Files', '*.csv'),))
        if not filename:
            return
        print("filename:", filename)
        with open(filename, 'w') as f:
            for result in self.results:
                f.write(f"{result[0]},{result[1]},{result[2]},{result[3]}\n")

    def run(self):
        self.root.mainloop()

    def quit(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor_thread.join()
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


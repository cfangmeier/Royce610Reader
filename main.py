import serial
import tkinter as tk
from tkinter import ttk

MOCK = True
REPORT = """\
========================================
           ROYCE INSTRUMENTS            
      SYSTEM 610 WIRE-PULL TESTER      
========================================
DATE: 02-03-2022 TIME: 07:21:38        
OPERATOR NAME: OPERATOR    1    
PART NUMBER  : PART        1    
----------------------------------------
    9      DESTRUCT TESTS
  9.61 gf  MEAN LOAD
  2.55 gf  STD DEV n-1
----------------------------------------
  1.95 gf  MEAN - 3*STD-DEV
----------------------------------------
 12.5  gf  MAX LOAD
  5.3  gf  MIN LOAD
----------------------------------------
UNDER PRESET LOAD
    0 TESTS <   0.1 gf
OVER PRESET LOAD
    0 TESTS > 100.0 gf
----------------------------------------
Test#  Force (gf) Failure mode    Code  
----------------------------------------
    1     0.6   NON-DESTRUCT        0  
    2     7.8   NO CODE ASSIGNED   13  
    3     5.3   NO CODE ASSIGNED   13  
    4     6.8   NO CODE ASSIGNED   13  
    5    10.7   NO CODE ASSIGNED   13  
    6    11.0   NO CODE ASSIGNED   13  
    7    11.7   NO CODE ASSIGNED   13  
    8    12.0   NO CODE ASSIGNED   13  
    9    12.5   NO CODE ASSIGNED   13  
   10     8.7   NO CODE ASSIGNED   13
"""


class MockPort:

    def __init__(self):
        self.lines = REPORT.splitlines()

    def readline(self):
        from time import sleep
        from random import random
        sleep(random()*10)
        return self.lines.pop(0)


class Monitor:

    def __init__(self):
        self.port_name = ""
        self.port: serial.Serial = None
        self.buffer = None

    @staticmethod
    def get_ports():
        from serial.tools import list_ports
        if MOCK:
            ports = ["COM1", "COM2", "COM3"]
        else:
            ports = list_ports.comports()
        print(f"Available COM ports: {ports}")
        return ports

    def open_port(self, port_name=None):
        if port_name is not None:
            self.port_name = port_name
        if not MOCK:
            self.port = serial.Serial(self.port_name, 9600)

    def close_port(self):
        if not MOCK:
            if self.port.isOpen():
                self.port.close()

    def get_report(self):
        pass


class UI:
    def __init__(self):
        self.monitor = Monitor()

        self.root = tk.Tk()
        frm = ttk.Frame(self.root, padding=10)

        frm.grid()
        ports = self.monitor.get_ports()
        clicked = tk.StringVar()
        if ports:
            clicked.set(ports[0])
        self.serial_option_menu = ttk.OptionMenu(self.root, clicked, "", *ports)
        self.serial_option_menu.grid(column=2, row=0)

        ttk.Label(frm, text="Hello World!").grid(column=0, row=0)
        ttk.Button(frm, text="Quite", command=self.root.destroy).grid(column=1, row=0)

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    ui = UI()
    ui.run()


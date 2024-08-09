import tkinter as tk
from tkinter import ttk
from tkinter.ttk import *
from functions import *
import sys


root = tk.Tk()
DFSwindow = FrontEnd(root)

# stdout will be printed in textbox 
stdoutFrame = tk.Frame( root )
stdoutFrame.pack(fill=BOTH)
stdoutFrame.rowconfigure(0, weight=1)
stdoutFrame.columnconfigure(0, weight=1)
console = tk.Text(stdoutFrame, height=20)
console.grid(column=0, row=0, sticky=(N, S, E, W))

def redirector(inputStr):
    console.insert(INSERT, inputStr)

sys.stdout.write = redirector #whenever sys.stdout.write is called, redirector is called.
sys.stderr.write = redirector

root.update()
root.minsize(root.winfo_width(), root.winfo_height())
root.protocol("WM_DELETE_WINDOW", DFSwindow.on_closing )
root.mainloop()
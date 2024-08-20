import sys
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.ttk import *
from functions import *
from timestamp import *


root = tk.Tk()                  # Root tkinter interface (contains DFS_Window and standard output console)
DFS_Window = FrontEnd(root)     # Contains

# stdout will be printed in textbox 
stdoutFrame = tk.Frame(root)
stdoutFrame.pack(fill=BOTH)
stdoutFrame.rowconfigure(0, weight=1)
stdoutFrame.columnconfigure(0, weight=1)
console = tk.Text(stdoutFrame, height=20)
console.grid(column=0, row=0, sticky=(N, S, E, W))

def redirector(inputStr):
    console.insert(INSERT, inputStr)

# When sys.std***.write is called (such as on print), call redirector to print in textbox
sys.stdout.write = redirector
sys.stderr.write = redirector

root.update()
root.minsize(root.winfo_width(), root.winfo_height())
root.protocol("WM_DELETE_WINDOW", DFS_Window.on_closing )
root.mainloop()
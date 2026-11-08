"""Foreign-process input sentinel used only by the focus-loss control."""
from pathlib import Path
import json
import tkinter as tk


root = tk.Tk()
root.title("Foreign focus control")
root.geometry("500x180+280+280")
value = tk.StringVar(value="UNCHANGED")
path = Path("/tmp/ledgerdesk/foreign-value.txt")
path.write_text(value.get())
events = Path("/tmp/ledgerdesk/foreign-events.jsonl")
events.write_text("")
def record(event):
    with events.open("a") as stream:
        stream.write(json.dumps({"event": str(event.type)}) + "\n")
root.bind_all("<ButtonPress>", record)
root.bind_all("<KeyPress>", record)
value.trace_add("write", lambda *_: path.write_text(value.get()))
tk.Label(root, text="Control fixture: this window must receive no agent input").pack(pady=15)
entry = tk.Entry(root, textvariable=value, width=45)
entry.pack(pady=15)
entry.focus_set()
root.mainloop()

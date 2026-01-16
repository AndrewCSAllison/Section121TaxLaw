import tkinter as tk
from tkinter import scrolledtext

from App.controller import load_file, submit

root = tk.Tk()
root.title("§121 GraphDB Pipeline")

ttl_text = scrolledtext.ScrolledText(root, width=100, height=20)
ttl_text.pack(pady=5)

load_btn = tk.Button(
    root,
    text="Load TTL File",
    command=lambda: load_file(ttl_text)
)
load_btn.pack(pady=5)

submit_btn = tk.Button(
    root,
    text="Submit to GraphDB",
    command=lambda: submit(ttl_text, output_text)
)
submit_btn.pack(pady=5)

output_text = scrolledtext.ScrolledText(root, width=100, height=20)
output_text.pack(pady=5)

root.mainloop()

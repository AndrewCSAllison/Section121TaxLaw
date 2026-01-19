import tkinter as tk
from tkinter import scrolledtext
from App.controller import load_file, submit, clear_repository

# -------------------------------
# Main Window
# -------------------------------
root = tk.Tk()
root.title("§121 GraphDB Pipeline")
root.geometry("950x600")  # width x height

# -------------------------------
# Frames for layout
# -------------------------------
# Left frame for buttons
button_frame = tk.Frame(root, width=200)
button_frame.pack(side="left", fill="y", padx=5, pady=5)

# Right frame for chat / conversation
chat_frame = tk.Frame(root)
chat_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

# -------------------------------
# Chat area (scrollable)
# -------------------------------
chat_text = scrolledtext.ScrolledText(chat_frame, wrap="word", state="disabled")
chat_text.pack(fill="both", expand=True)

# -------------------------------
# Input box for TTL / user text
# -------------------------------
input_text = tk.Text(chat_frame, height=4)
input_text.pack(fill="x", pady=5)

# -------------------------------
# Helper to append messages to chat
# -------------------------------
def append_chat(message, sender="User"):
    chat_text.configure(state="normal")
    chat_text.insert("end", f"{sender}: {message}\n\n")
    chat_text.configure(state="disabled")
    chat_text.see("end")

# -------------------------------
# Button callbacks
# -------------------------------
def on_load_file():
    load_file(input_text)
    append_chat("Loaded TTL file into input.", sender="System")

def on_submit():
    content = input_text.get("1.0", "end").strip()
    if content:
        append_chat(content, sender="User")
    submit(input_text, chat_text)
    append_chat("Submission complete.", sender="System")

def on_clear_repo():
    if tk.messagebox.askyesno("Confirm", "Are you sure you want to clear the repository?"):
        clear_repository()
        append_chat("Repository cleared and fresh TTL files uploaded.", sender="System")

# -------------------------------
# Buttons
# -------------------------------
tk.Button(button_frame, text="Load TTL File", width=20, command=on_load_file).pack(pady=5)
tk.Button(button_frame, text="Submit / Execute Rules", width=20, command=on_submit).pack(pady=5)
tk.Button(button_frame, text="Clear Repository", width=20, command=on_clear_repo).pack(pady=5)

# -------------------------------
# Start the GUI
# -------------------------------
root.mainloop()

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from gpt4all import GPT4All

# ------------------------
# Initialize model
# ------------------------
model_path = "gpt4all-lora-quantized.bin"
model = GPT4All(model_path)

# ------------------------
# GUI
# ------------------------
root = tk.Tk()
root.title("TTL File Formatter (Multi-File)")
root.geometry("700x500")

output_text = scrolledtext.ScrolledText(root, wrap=tk.WORD)
output_text.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

# Function to select multiple input files
def upload_files():
    file_paths = filedialog.askopenfilenames(
        title="Select Scenario Files",
        filetypes=[("Text or TTL Files", "*.txt *.ttl"), ("All Files", "*.*")]
    )
    if file_paths:
        combined_data = ""
        for idx, path in enumerate(file_paths, start=1):
            with open(path, 'r', encoding='utf-8') as f:
                combined_data += f"\n--- File {idx}: {path.split('/')[-1]} ---\n"
                combined_data += f.read() + "\n"
        generate_ttl(combined_data)

# Function to generate TTL
def generate_ttl(combined_text):
    prompt = f"""
You are an expert TTL formatter. Format the following taxpayer scenario data into a single valid TTL file.
- Preserve all relevant data from each file.
- Follow TTL syntax strictly.
- Do not add unnecessary triples.
- Clearly handle data from multiple sources.

Input Files:
{combined_text}

Output TTL:
"""
    try:
        response = model.generate(prompt, max_tokens=2048)
        output_text.delete("1.0", tk.END)
        output_text.insert(tk.END, response)
    except Exception as e:
        messagebox.showerror("Error", str(e))

upload_btn = tk.Button(root, text="Upload Scenario Files", command=upload_files)
upload_btn.pack(pady=5)

root.mainloop()

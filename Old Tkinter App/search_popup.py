# search_popup.py
import tkinter as tk

class SearchPopup(tk.Toplevel):
    def __init__(self, parent, data):
        super().__init__(parent)
        self.data = data  # Dictionary mapping strings to counts
        self.title("Search Popup")
        self.geometry("400x350")

        self.result = None  # To store the final result

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.update_list)

        # Search entry
        self.entry = tk.Entry(self, textvariable=self.search_var)
        self.entry.pack(pady=10, padx=10, fill=tk.X)
        self.entry.focus_set()
        self.bind("<Return>", lambda event: self.on_submit())

        # Listbox for displaying search results
        self.listbox = tk.Listbox(self)
        self.listbox.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        # Submit button
        submit_button = tk.Button(self, text="Submit", command=self.on_submit)
        
        submit_button.pack(pady=10)

        # Populate the listbox initially
        self.update_list()

    def update_list(self, *args):
        search_text = self.search_var.get().lower()
        filtered = sorted(
            ((k, v) for k, v in self.data.items() if search_text in k.lower()),
            key=lambda x: (-x[1], x[0].lower())
        )

        self.listbox.delete(0, tk.END)
        for key, count in filtered:
            self.listbox.insert(tk.END, f"{key}")

    def on_select(self, event):
        selection = self.listbox.curselection()
        if selection:
            key = self.listbox.get(selection[0])
            self.search_var.set(key)
            self.entry.icursor(tk.END)

    def on_submit(self):
        self.result = self.search_var.get()
        self.destroy()

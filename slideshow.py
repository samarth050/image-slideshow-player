import os
import random
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from PIL import Image, ImageTk
import ctypes
import subprocess
import shutil
from tkinter import simpledialog
from tkinter import ttk
import threading
import re
# ---------------- CONSTANTS ----------------
SEVEN_ZIP = r"C:\Program Files\7-Zip\7z.exe"
IMAGES_ARCHIVE = "images.7z"
ARCHIVE_PASSWORD = "snoopy050"
CREATE_NO_WINDOW = 0x08000000
IMAGES_ROOT = "images"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
DEFAULT_DURATION = 5  # seconds
images_compressed = False
# ---- UI globals (initialized in build_ui) ----
frame = None
controls_frame = None
category_listbox = None
slideshow_frame = None
slideshow_label = None
start_btn = None
stop_btn = None
progress = None
status_var = None

def build_ui():
    global frame, controls_frame
    global category_listbox, slideshow_frame, slideshow_label
    global start_btn, stop_btn, progress, status_var
    global duration_var, mode_var, fullscreen_var

    root.title("Image Slideshow Player")
    root.geometry("920x920")

    frame = tk.Frame(root, padx=12, pady=12)
    frame.pack(fill=tk.BOTH, expand=True)

    # ---------- CONTROLS ----------
    # ---------- TOP CONTROLS (2-column layout) ----------
    top_controls = tk.Frame(frame)
    top_controls.pack(fill=tk.X, expand=False)

    # LEFT: Categories
    left_panel = tk.Frame(top_controls)
    left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

    tk.Label(
        left_panel,
        text="Image Categories",
        font=("Segoe UI", 10, "bold")
    ).pack(anchor="w")

    list_frame = tk.Frame(left_panel)
    list_frame.pack(fill=tk.BOTH, expand=True)

    category_listbox = tk.Listbox(
        list_frame,
        selectmode=tk.MULTIPLE,
        height=10,           # 👈 smaller vertical footprint
        width=28,            # 👈 fixed width
        exportselection=False
    )
    scrollbar = tk.Scrollbar(
        list_frame,
        orient=tk.VERTICAL,
        command=category_listbox.yview
    )
    category_listbox.config(yscrollcommand=scrollbar.set)

    category_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # RIGHT: Controls
    right_panel = tk.Frame(top_controls)
    right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    tk.Label(right_panel, text="Duration per image (seconds):").pack(anchor="w")
    duration_var = tk.IntVar(value=DEFAULT_DURATION)
    tk.Spinbox(
        right_panel,
        from_=1,
        to=60,
        textvariable=duration_var,
        width=6
    ).pack(anchor="w")

    tk.Label(right_panel, text="").pack()

    mode_var = tk.StringVar(value="random")
    tk.Label(right_panel, text="Playback Mode:").pack(anchor="w")
    tk.Radiobutton(
        right_panel,
        text="Random",
        variable=mode_var,
        value="random"
    ).pack(anchor="w")
    tk.Radiobutton(
        right_panel,
        text="Sequential",
        variable=mode_var,
        value="seq"
    ).pack(anchor="w")

    tk.Label(right_panel, text="").pack()

    fullscreen_var = tk.BooleanVar(value=True)
    tk.Checkbutton(
        right_panel,
        text="Fullscreen",
        variable=fullscreen_var
    ).pack(anchor="w")

    # Buttons
    btn_frame = tk.Frame(right_panel)
    btn_frame.pack(pady=10, anchor="w")

    start_btn = tk.Button(
        btn_frame,
        text="Start Slideshow",
        width=16,
        command=start_slideshow
    )
    start_btn.pack(side=tk.LEFT, padx=5)

    stop_btn = tk.Button(
        btn_frame,
        text="Stop",
        width=10,
        command=stop_slideshow
    )
    stop_btn.pack(side=tk.LEFT)

    tk.Button(
        right_panel,
        text="Compress Images (Hide)",
        width=22,
        command=compress_images
    ).pack(pady=3, anchor="w")

    tk.Button(
        right_panel,
        text="Extract Images",
        width=22,
        command=extract_images
    ).pack(pady=3, anchor="w")

    # ---------- Progress Bar ----------
    status_var = tk.StringVar(value="Ready")
    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.pack(fill=tk.X, pady=5)

    tk.Label(
        frame,
        textvariable=status_var,
        fg="gray"
    ).pack(anchor="w")
    # ---------- SLIDESHOW ----------
    slideshow_frame = tk.LabelFrame(
        frame,
        text="Slideshow Preview",
        padx=5,
        pady=5
    )
    slideshow_frame.pack(fill=tk.BOTH, expand=True, pady=8)
    slideshow_frame.configure(height=350)
    slideshow_frame.pack_propagate(False)

    slideshow_label = tk.Label(slideshow_frame, bg="black")
    slideshow_label.pack(fill=tk.BOTH, expand=True)
    slideshow_label.config(
        text="No slideshow running",
        fg="gray",
        font=("Segoe UI", 10)
    )


# ---------------------------------------

def sync_compression_state():
    global images_compressed

    if os.path.isdir(IMAGES_ROOT):
        images_compressed = False
        set_slideshow_enabled(True)
        status_var.set("Images available")
    elif os.path.exists(IMAGES_ARCHIVE):
        images_compressed = True
        set_slideshow_enabled(False)
        status_var.set("Images are compressed")
    else:
        images_compressed = True
        set_slideshow_enabled(False)
        status_var.set("No images found")


def set_controls_enabled(enabled):
    state = tk.NORMAL if enabled else tk.DISABLED
    start_btn.config(state=state)
    stop_btn.config(state=state)

def update_progress(value, text=None):
    
    if text:
        root.after(0, lambda: status_var.set(text))

def reset_progress():
    update_progress(0, "Ready")

def refresh_categories():
    category_listbox.delete(0, tk.END)
    for cat in get_categories():
        category_listbox.insert(tk.END, cat)


def set_hidden(path: str):
    FILE_ATTRIBUTE_HIDDEN = 0x02
    attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    if attrs == -1:
        return
    ctypes.windll.kernel32.SetFileAttributesW(
        str(path),
        attrs | FILE_ATTRIBUTE_HIDDEN
    )


def compress_images():
    global images_compressed

    if not os.path.isdir(IMAGES_ROOT):
        root.after(0, lambda: messagebox.showerror("Error", "Images folder not found."))
        return

    root.after(0, lambda: status_var.set("Compressing images..."))
    
    cmd = [
        SEVEN_ZIP,
        "a",
        "-t7z",
        "-y",
        f"-p{ARCHIVE_PASSWORD}",
        "-mhe=on",
        IMAGES_ARCHIVE,
        os.path.join(IMAGES_ROOT, "*")
    ]

    def worker():
        root.after(0, lambda: set_controls_enabled(False))
        root.after(0, progress.start)

        try:
            if os.path.exists(IMAGES_ARCHIVE):
                os.remove(IMAGES_ARCHIVE)

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=CREATE_NO_WINDOW
            )
            process.wait()

            set_hidden(IMAGES_ARCHIVE)
            shutil.rmtree(IMAGES_ROOT)

            images_compressed = True
            root.after(0, lambda: set_slideshow_enabled(False))
            root.after(0, lambda: status_var.set("Compression complete"))
            root.after(0, refresh_categories)
            root.after(0, lambda: messagebox.showinfo(
                "Success",
                "Images compressed successfully."
            ))
            images_compressed = True
            root.after(0, sync_compression_state)

        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", str(e)))

        finally:
            root.after(0, progress.stop)
            root.after(0, lambda: set_controls_enabled(True))
    threading.Thread(target=worker, daemon=True).start()

def extract_images():
    global images_compressed

    if not os.path.exists(IMAGES_ARCHIVE):
        root.after(0, lambda: messagebox.showerror("Error", "Archive not found."))
        return

    pwd = simpledialog.askstring(
        "Password Required",
        "Enter archive password:",
        show="*"
    )

    if not pwd:
        return

    root.after(0, lambda: status_var.set("Verifying password..."))
    

    def worker():
        try:
            # Test password
            test_cmd = [
                SEVEN_ZIP,
                "t",
                f"-p{pwd}",
                IMAGES_ARCHIVE
            ]

            subprocess.run(
                test_cmd,
                check=True,
                creationflags=CREATE_NO_WINDOW
            )
            
        except subprocess.CalledProcessError:
            reset_progress()
            root.after(0, lambda: messagebox.showerror("Error", "Incorrect password."))
            return

        try:
            root.after(0, lambda: status_var.set("Extracting images..."))

            extract_cmd = [
                SEVEN_ZIP,
                "x",
                "-y",
                f"-p{pwd}",
                IMAGES_ARCHIVE,
                f"-o{IMAGES_ROOT}"
            ]
            

            process = subprocess.Popen(
                extract_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=CREATE_NO_WINDOW
            )
            root.after(0, progress.start)
            root.after(0, lambda: set_controls_enabled(False))
            process.wait()
            root.after(0, progress.stop)
            nested = os.path.join(IMAGES_ROOT, IMAGES_ROOT)
            if os.path.exists(IMAGES_ARCHIVE):
                os.remove(IMAGES_ARCHIVE)

            if os.path.isdir(nested):
                for item in os.listdir(nested):
                    shutil.move(
                        os.path.join(nested, item),
                        IMAGES_ROOT
                    )
                os.rmdir(nested)
            images_compressed = False
            root.after(0, sync_compression_state)

            root.after(0, lambda: set_controls_enabled(True))
         

            # Hide extracted folder
            """
            if os.path.isdir(IMAGES_ROOT):
                set_hidden(IMAGES_ROOT)
            """
            images_compressed = False
            root.after(0, lambda: set_slideshow_enabled(True))

            update_progress(100, "Extraction complete")
            root.after(0, lambda: messagebox.showinfo("Success", "Images extracted and hidden."))
            root.after(0, refresh_categories)

        except Exception as e:
            reset_progress()
            root.after(0, lambda: messagebox.showerror("Error", str(e)))

    threading.Thread(target=worker, daemon=True).start()


def get_categories():
    if not os.path.isdir(IMAGES_ROOT):
        return []
    return sorted(
        d for d in os.listdir(IMAGES_ROOT)
        if os.path.isdir(os.path.join(IMAGES_ROOT, d))
    )


def collect_images(categories):
    images = []
    for cat in categories:
        folder = os.path.join(IMAGES_ROOT, cat)
        for root, _, files in os.walk(folder):
            for f in files:
                if Path(f).suffix.lower() in IMAGE_EXTS:
                    images.append(os.path.join(root, f))
    return images


def set_slideshow_enabled(enabled: bool):
    state = tk.NORMAL if enabled else tk.DISABLED
    start_btn.config(state=state)
    stop_btn.config(state=state)

def start_slideshow():
    if images_compressed:
        messagebox.showwarning(
            "Images Unavailable",
            "Images are compressed. Extract them first."
        )
        return

    global slideshow_player

    selected = [
        category_listbox.get(i)
        for i in category_listbox.curselection()
    ]

    if not selected:
        messagebox.showwarning("Selection required", "Please select at least one category.")
        return

    images = collect_images(selected)
    if not images:
        messagebox.showwarning("No images", "No images found in selected folders.")
        return

    # 🔥 HERE is the fix
    if fullscreen_var.get():
        slideshow_player = FullscreenSlideShowPlayer(
            root,
            images,
            duration_var.get(),
            mode_var.get() == "random"
        )
    else:
        slideshow_player = EmbeddedSlideShowPlayer(
            slideshow_label,
            images,
            duration_var.get(),
            mode_var.get() == "random"
        )

    slideshow_player.start()


def stop_slideshow():
    global slideshow_player
    if slideshow_player:
        slideshow_player.stop()
        slideshow_player = None
class FullscreenSlideShowPlayer:
    def __init__(self, parent, images, delay_sec, random_mode):
        self.parent = parent
        self.images = images[:]
        self.delay = int(delay_sec * 1000)
        self.random_mode = random_mode
        self.index = 0
        self.running = False

        self.win = tk.Toplevel(parent)
        self.win.configure(bg="black")
        self.win.attributes("-fullscreen", True)
        self.win.bind("<Escape>", lambda e: self.stop())

        self.label = tk.Label(self.win, bg="black")
        self.label.pack(expand=True, fill=tk.BOTH)

    def start(self):
        self.running = True
        self.show_next()

    def stop(self):
        self.running = False
        self.win.destroy()

    def show_next(self):
        if not self.running or not self.images:
            return

        if self.random_mode:
            path = random.choice(self.images)
        else:
            path = self.images[self.index]
            self.index = (self.index + 1) % len(self.images)

        try:
            img = Image.open(path)
            w = self.win.winfo_width()
            h = self.win.winfo_height()
            img.thumbnail((w, h), Image.LANCZOS)
            self.tk_img = ImageTk.PhotoImage(img)
            self.label.config(image=self.tk_img)
        except Exception:
            pass

        self.win.after(self.delay, self.show_next)

class EmbeddedSlideShowPlayer:
    def __init__(self, label, images, delay_sec, random_mode):
        self.label = label
        self.images = images[:]
        self.delay = int(delay_sec * 1000)
        self.random_mode = random_mode
        self.index = 0
        self.running = False
        self.tk_img = None

    def start(self):
        self.running = True
        self.show_next()

    def stop(self):
        self.running = False
        self.label.config(image="")

    def show_next(self):
        if not self.running or not self.images:
            return

        if self.random_mode:
            path = random.choice(self.images)
        else:
            path = self.images[self.index]
            self.index = (self.index + 1) % len(self.images)

        try:
            img = Image.open(path)

            w = self.label.winfo_width()
            h = self.label.winfo_height()
            if w > 10 and h > 10:
                img.thumbnail((w, h), Image.LANCZOS)

            self.tk_img = ImageTk.PhotoImage(img)
            self.label.config(image=self.tk_img)
        except Exception:
            pass

        self.label.after(self.delay, self.show_next)

root = tk.Tk()
build_ui()
sync_compression_state()
refresh_categories()
root.mainloop()



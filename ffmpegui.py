import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
import subprocess
import json
import threading
import time
import re
import logging

logging.basicConfig(level=logging.INFO)


class FFMpegGUI:
    def __init__(self):
        self.video_streams = []
        self.audio_streams = []
        self.subtitle_streams = []
        self.video_stream_list = None
        self.audio_stream_list = None
        self.subtitle_stream_list = None
        self.audio_selection = []
        self.video_selection = []
        self.subtitle_selection = []

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.root = ctk.CTk()

        self.root.title("FFmpeg GUI")
        self.input_file_var = tk.StringVar()
        self.preset_var = tk.StringVar()
        self.video_duration_seconds = 0

        self.create_GUI()

    def select_file(self):
        file_path = filedialog.askopenfilename()
        self.input_file_var.set(file_path)
        self.show_file_details(file_path)

    def convert_time_to_seconds(self, time_str):
        h, m, s = map(float, time_str.split(':'))
        return h * 3600 + m * 60 + s

    def update_progress_bar(self):
        time_pattern = re.compile(r"time=(\d+:\d+:\d+\.\d+)")

        while True:
            if self.process is not None:
                if self.process.poll() is not None:
                    break
                line = self.process.stderr.readline().strip()
                if line == '' and self.process.poll() is not None:
                    break
                # if line and "frame=" in line:
                match = time_pattern.search(line)
                if match:
                    current_time = match.group(1)
                    current_time_seconds = self.convert_time_to_seconds(
                        current_time)
                    progress = (current_time_seconds /
                                self.video_duration_seconds) * 100
                    progress = min(max(progress, 0), 100)
                    self.root.after(10, lambda: self.progress_bar.configure(
                        text=str(int(progress)) + "%"))
                time.sleep(0.01)
        # once we've finished, statically set to 100% because progress calculation is fuzzy
        self.root.after(10, lambda: self.progress_bar.configure(text="100%"))

    def show_file_details(self, file_path):
        cmd = ["ffprobe", "-v", "quiet", "-print_format",
               "json", "-show_streams", "-show_format", file_path]
        data = json.loads(subprocess.run(
            cmd, capture_output=True, text=True).stdout)
        format_info = data.get('format', {})
        logging.debug(data)
        logging.debug(f"Format-Info: {format_info}")
        duration = float(format_info.get('duration', 1))
        self.video_duration_seconds = duration

        self.video_streams = [
            stream for stream in data["streams"] if stream["codec_type"] == "video"]
        self.audio_streams = [
            stream for stream in data["streams"] if stream["codec_type"] == "audio"]
        self.subtitle_streams = [
            stream for stream in data["streams"] if stream["codec_type"] == "subtitle"]

        self.audio_stream_list.delete(0, tk.END)
        self.video_stream_list.delete(0, tk.END)
        self.subtitle_stream_list.delete(0, tk.END)

        for i, audio in enumerate(self.audio_streams, 1):
            language = audio['tags']['language'] if 'tags' in audio and 'language' in audio['tags'] else 'unknown'
            self.audio_stream_list.insert(
                i, f"{audio['codec_name']} {audio['channels']} channels ({language})")

        for i, video in enumerate(self.video_streams, 1):
            language = video['tags']['language'] if 'tags' in video and 'language' in video['tags'] else 'unknown'
            self.video_stream_list.insert(
                i, f"{video['codec_name']} {video['width']}x{video['height']} ({language})")

        for i, subtitle in enumerate(self.subtitle_streams, 1):
            language = subtitle['tags']['language'] if 'tags' in subtitle and 'language' in subtitle['tags'] else 'unknown'
            self.subtitle_stream_list.insert(
                i, f"{subtitle['codec_name']} ({language})")

    def _extract_stream_info(self, stream):
        codec_type, codec_name, index = stream["codec_type"], stream["codec_name"], stream["index"]
        stream_data = {
            "index": index,
            "type": codec_type,
            "codec": codec_name
        }
        if codec_type == "audio":
            return self._audio_info(stream, stream_data)
        elif codec_type == "subtitle":
            return self._subtitle_info(stream, stream_data)
        else:
            return self._video_info(stream, stream_data)

    def _audio_info(self, stream):
        stream_data = {
            "index": stream["index"],
            "type": stream["codec_type"],
            "codec": stream["codec_name"]
        }
        stream_data["channels"] = channels = stream["channels"]
        stream_data["language"] = language = stream.get(
            'tags', {}).get('language', 'unknown')
        stream_data["details"] = f"Audio - Codec: {stream_data['codec']}, Channel(s): {channels}, Language: {language}"
        return stream_data

    def _subtitle_info(self, stream):
        stream_data = {
            "index": stream["index"],
            "type": stream["codec_type"],
            "codec": stream["codec_name"]
        }
        stream_data["language"] = language = stream.get(
            'tags', {}).get('language', 'unknown')
        stream_data["details"] = f"Subtitle - Language: {language}"
        return stream_data

    def _video_info(self, stream):
        stream_data = {
            "index": stream["index"],
            "type": stream["codec_type"],
            "codec": stream["codec_name"]
        }
        stream_data["resolution"] = resolution = f"{stream['width']}x{stream['height']}"
        stream_data["details"] = f"Video - Codec: {stream_data['codec']}, Resolution: {resolution}"
        return stream_data

    def start_conversion(self):
        selected_audio_indices = self.audio_stream_list.curselection()
        selected_video_indices = self.video_stream_list.curselection()
        selected_subtitle_indices = self.subtitle_stream_list.curselection()

        if not (selected_audio_indices or selected_video_indices or selected_subtitle_indices):
            messagebox.showerror(
                "Error", "Please select streams for conversion.")
            return

        selected_audio_streams = [self._audio_info(
            self.audio_streams[i]) for i in selected_audio_indices]
        selected_video_streams = [self._video_info(
            self.video_streams[i]) for i in selected_video_indices]
        selected_subtitle_streams = [self._subtitle_info(
            self.subtitle_streams[i]) for i in selected_subtitle_indices]

        selected_streams = selected_audio_streams + \
            selected_video_streams + selected_subtitle_streams

        input_file = self.input_file_var.get()
        output_file = input_file.replace(".mkv", "_converted.mp4")

        cmd = ["ffmpeg", "-y", "-i", self.input_file_var.get(), "-preset",
               self.preset_var.get()]

        for stream in selected_streams:
            if stream['type'] == "audio":
                cmd.extend(
                    ["-map", f"0:{stream['index']}", "-c:a", stream['codec']])
            elif stream['type'] == "video":
                cmd.extend(["-map", f"0:{stream['index']}", "-c:v", "libx264"])
            elif stream['type'] == "subtitle":
                cmd.extend(
                    ["-map", f"0:{stream['index']}", "-scodec", stream['codec']])

        cmd.append(output_file)

        self.process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.thread = threading.Thread(target=self.update_progress_bar)
        self.thread.start()

        self.root.after(100, self.check_thread)

    def cancel_conversion(self):
        if self.process:
            self.process.terminate()  # Sendet ein SIGTERM-Signal
            self.process = None

    def check_thread(self):
        if self.process and self.process.poll() is None:
            self.root.after(100, self.check_thread)   # Retry after 100ms
        else:
            if self.process:
                stdout, stderr = self.process.communicate()
                self.process = None
                if stdout:
                    print(f'STDOUT:{stdout}')
                if stderr:
                    print(f'STDERR:{stderr}')
                self.thread.join()  # Stop the Thread

    def create_GUI(self):
        input_frame = ctk.CTkFrame(self.root)
        input_frame.pack(padx=10, pady=5, fill=ctk.X)

        label_input = ctk.CTkLabel(input_frame, text="Input File:")
        label_input.pack(side=ctk.LEFT)

        self.input_entry = ctk.CTkEntry(
            input_frame, textvariable=self.input_file_var, width=300)
        self.input_entry.pack(side=ctk.LEFT, padx=5)

        btn_select = ctk.CTkButton(input_frame, text="Select",
                                   command=self.select_file)
        btn_select.pack(side=ctk.LEFT)

        preset_frame = ctk.CTkFrame(self.root)
        preset_frame.pack(padx=10, pady=5, fill=ctk.X)

        lbl_preset = ctk.CTkLabel(preset_frame, text="Preset:")
        lbl_preset.pack(side=ctk.LEFT)

        PRESETS = ["ultrafast", "superfast", "veryfast", "faster",
                   "fast", "medium", "slow", "slower", "veryslow"]
        self.preset_var.set(PRESETS[5])

        preset_combobox = ctk.CTkComboBox(
            preset_frame, values=PRESETS, variable=self.preset_var, state="readonly")
        preset_combobox.pack(side=ctk.LEFT, padx=5)

        listbox_frame = ctk.CTkFrame(self.root)
        listbox_frame.pack(padx=10, pady=5)

        video_label = ctk.CTkLabel(
            listbox_frame, text="Video Streams", anchor='w')
        video_label.grid(row=0, column=0, sticky='w')

        self.video_stream_list = tk.Listbox(
            listbox_frame, height=10, width=26, selectmode=tk.MULTIPLE, exportselection=False)
        self.video_stream_list.grid(row=1, column=0, padx=5)

        audio_label = ctk.CTkLabel(
            listbox_frame, text="Audio Streams", anchor='w')
        audio_label.grid(row=0, column=1, sticky='w')

        self.audio_stream_list = tk.Listbox(
            listbox_frame, height=10, width=26, selectmode=tk.MULTIPLE, exportselection=False)
        self.audio_stream_list.grid(row=1, column=1, padx=5)

        subtitle_label = ctk.CTkLabel(
            listbox_frame, text="Subtitle Streams", anchor='w')
        subtitle_label.grid(row=0, column=2, sticky='w')

        self.subtitle_stream_list = tk.Listbox(
            listbox_frame, height=10, width=26, selectmode=tk.MULTIPLE, exportselection=False)
        self.subtitle_stream_list.grid(row=1, column=2, padx=5)

        self.progress_bar = ctk.CTkLabel(
            self.root, text="0%", font=("Helvetica", 18, 'bold'))
        self.progress_bar.pack(padx=10, pady=5)

        btn_convert = ctk.CTkButton(
            self.root, text="Start Conversion", command=self.start_conversion)
        btn_convert.pack(padx=10, pady=5)

        cancel_button = ctk.CTkButton(
            self.root, text="Cancel", command=self.cancel_conversion)
        cancel_button.pack()

        self.root.mainloop()


if __name__ == "__main__":
    FFMpegGUI()

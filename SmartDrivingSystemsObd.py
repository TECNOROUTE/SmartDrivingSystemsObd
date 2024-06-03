import cv2
import time
import os
import tkinter as tk
from tkinter import messagebox
from picamera2 import Picamera2, Preview
from picamera2.encoders import H264Encoder
from threading import Thread, Event
from subprocess import call
import obd
import csv
from datetime import datetime
from datetime import timedelta
from PIL import Image, ImageTk
from libcamera import Transform

def record_with_opencv(start_event, stop_event, output_path, obd_connection, preview_label):
    cap = cv2.VideoCapture(0)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(os.path.join(output_path, 'opencv_output.mp4'), fourcc, 20.0, (640, 480))

    start_event.wait()

    while not stop_event.is_set():
        ret, frame = cap.read()
        if ret:
            out.write(frame)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_pil = Image.fromarray(frame_rgb)
            frame_pil = frame_pil.resize((320, 240), Image.ANTIALIAS)
            frame_tk = ImageTk.PhotoImage(frame_pil)
            preview_label.config(image=frame_tk)
            preview_label.image = frame_tk
            if cv2.waitKey(1) & 0xFF == ord('q'):
                stop_event.set()
                break
        else:
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()

def record_with_picamera2(start_event, stop_event, output_path, obd_connection, preview_label):
    picam2 = Picamera2()
    preview_config = picam2.create_preview_configuration()
    picam2.configure(preview_config)
    picam2.start_preview(Preview.QT)

    video_config = picam2.create_video_configuration(main={"size": (640, 480)})
    picam2.configure(video_config)
    encoder = H264Encoder(10000000)

    start_event.wait()
    h264_path = os.path.join(output_path, 'picamera_output.h264')
    mp4_path = os.path.join(output_path, 'picamera_output.mp4')
    picam2.start_recording(encoder, h264_path)

    while not stop_event.is_set():
        time.sleep(0.1)

    picam2.stop_preview()
    picam2.stop_recording()

    call(['ffmpeg', '-i', h264_path, '-c:v', 'copy', mp4_path])


def check_obd_connection():
    try:
        obd_connection = obd.OBD()
        if(obd_connection == True):
            return True
        else:
            return False
        obd_connection.close()
    except Exception as e:
        print("OBD Connection Error:", e)
        return False


def check_camera_connection():
    cap = cv2.VideoCapture(0)
    connected = cap.isOpened()
    cap.release()
    return connected

def update_status_labels():
    global obd_label, camera_label
    obd_connected = check_obd_connection()
    camera_connected = check_camera_connection()
    if obd_connected:
        obd_label.config(text="OBD: Connected", fg="green")
    else:
        obd_label.config(text="OBD: Disconnected", fg="red")
    if camera_connected:
        camera_label.config(text="Camera: Connected", fg="green")
    else:
        camera_label.config(text="Camera: Disconnected", fg="red")
    obd_label.after(1000, update_status_labels)

def read_obd_data(obd_connection, csv_writer):
    global start_time  # Ba?lang?ç zaman?n? global olarak kullanal?m
    while True:
        cmd = obd.commands.SPEED
        response = obd_connection.query(cmd)
        if response.is_null() or response.value is None:  # E?er response bo? ise veya de?eri yoksa
            speed = 0
        else:
            speed = response.value.magnitude
        timestamp = start_time.strftime('%H:%M:%S')
        start_time += timedelta(seconds=10)
        csv_writer.writerow([timestamp, speed])
        time.sleep(10)
    print("Timestamp:", timestamp)
    print("Speed:", speed)

def start_recording():
    global opencv_thread, picamera_thread, obd_thread, start_event, stop_event, output_path, obd_connection, start_time

    output_path = 'video_records'
    os.makedirs(output_path, exist_ok=True)

    start_event = Event()
    stop_event = Event()

    obd_connection = obd.OBD()
    start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)  # Gün içindeki s?f?r saatine ayarlayal?m

    with open(os.path.join(output_path, 'obd_data.csv'), 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['Time', 'Speed'])

        obd_thread = Thread(target=read_obd_data, args=(obd_connection, csv_writer,))
        obd_thread.start()

        opencv_thread = Thread(target=record_with_opencv, args=(start_event, stop_event, output_path, obd_connection, preview_label,))
        picamera_thread = Thread(target=record_with_picamera2, args=(start_event, stop_event, output_path, obd_connection, preview_label,))

        opencv_thread.start()
        picamera_thread.start()

        start_event.set()

        start_button.config(state="disabled")
        stop_button.config(state="active")
        status_label.config(text="Recording Started")

def stop_recording():
    global stop_event
    if stop_event:
        stop_event.set()
        start_button.config(state="active")
        stop_button.config(state="disabled")
        status_label.config(text="Recording Stopped")

root = tk.Tk()
root.title("Smart Driving Systems Driver Recorder")
root.geometry("600x400")

obd_label = tk.Label(root, text="OBD: Disconnected", font=("Helvetica", 12), fg="red")
obd_label.pack(pady=5)
camera_label = tk.Label(root, text="Camera: Disconnected", font=("Helvetica", 12), fg="red")
camera_label.pack(pady=5)

title_label = tk.Label(root, text="Drive Recorder Application", font=("Helvetica", 16))
title_label.pack(pady=10)

preview_label = tk.Label(root)
preview_label.pack()

button_frame = tk.Frame(root)
button_frame.pack()

start_button = tk.Button(button_frame, text="Start", command=start_recording, bg="green", fg="white", padx=20, pady=10, font=("Helvetica", 12))
start_button.pack(side=tk.LEFT, padx=5)

stop_button = tk.Button(button_frame, text="Stop", command=stop_recording, bg="red", fg="white", padx=20, pady=10, font=("Helvetica", 12), state="disabled")
stop_button.pack(side=tk.LEFT, padx=5)

status_label = tk.Label(root, text="Waiting to Start Recording", font=("Helvetica", 12))
status_label.pack(pady=10)

update_status_labels()

root.mainloop()
import multiprocessing
from cvzone.SerialModule import SerialObject
import cv2
from ultralytics import YOLO
import speech_recognition as sr
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from datetime import datetime
from ttkthemes import ThemedStyle
import socket
import pygame

def play_sound(sound_file, duration):
    pygame.mixer.init()
    pygame.mixer.music.load(sound_file)
    pygame.mixer.music.play()
    time.sleep(duration)
    pygame.mixer.music.stop()

def warning_sound():
    sound_file_path = "sound.mp3"
    duration = 0.5
    play_sound(sound_file_path, duration)

def callback(recognizer, audio):
        try:
          print(recognizer.recognize_google(audio))
        # handles any api/voice errors  errors
        except sr.RequestError:
          print( "There was an issue in handling the request, please try again")
        except sr.UnknownValueError:
          print("Unable to Recognize speech")

class VideoProcess(multiprocessing.Process):
    def __init__(self, sendFrame, signalCam, check_destroy, signal_safe):
        multiprocessing.Process.__init__(self)
        self.sendFrame = sendFrame
        self.signalCam = signalCam
        self.check_destroy = check_destroy
        self.signal_safe = signal_safe

    def run(self):
        model = YOLO("yolov8s.pt")
        cap = cv2.VideoCapture(0)

        cnt = -1 #đếm số người hiện tại
        cnt_safe_person = -1 #đếm số người đang an toàn
        check_safe = False
        confirm_safe = True
        while True:
            # Đọc khung hình từ webcam
            ret, frame = cap.read()

            results = model(frame, conf = 0.5)
            xyxy = results[0].cpu().boxes.xyxy.tolist()
        
            cls = results[0].boxes.cls.tolist()
            indices = [i for i, x in enumerate(cls) if x == 0.0]
            cnt = len(indices)
            for index in indices:
                [x1, y1, x2, y2] = xyxy[index]
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        
            #mặc định an toàn
            signal = [1,0]
            
            if not self.signal_safe.empty():
                num = self.signal_safe.get()
                if num == 1: #bật chống trộm hoặc xác nhận an toàn
                    check_safe = True #bật chống trộm
                    cnt_safe_person = cnt
                    confirm_safe = True
                else:
                    check_safe = False #tắt chống trộm
            #gửi cảnh báo
            if check_safe:
                if cnt_safe_person < cnt or confirm_safe == False:#ko an toàn
                    signal = [0,1]
                    confirm_safe = False
                    warning_sound()
                elif cnt_safe_person > cnt:
                    cnt_safe_person = cnt#người trong khung ra khỏi
                
            else:
                cnt = cnt_safe_person

            self.signalCam.put(signal)
            self.sendFrame.put(frame)

            if not self.check_destroy.empty(): 
                break
            #time.sleep(0.1)

        # Giải phóng webcam và đóng cửa sổ hiển thị
        cap.release()
        cv2.destroyAllWindows()

class AudioProcess(multiprocessing.Process):
    def __init__(self, signalVoice, voice_time, voice_destroy, voice_text):
        multiprocessing.Process.__init__(self)
        self.signalVoice = signalVoice
        self.voice_time = voice_time
        self.voice_destroy = voice_destroy
        self.voice_text = voice_text

    def run(self):
        r = sr.Recognizer()
        mic = sr.Microphone()
        with mic as source:
            audio = r.listen_in_background(source, callback)
        print("Starting speech recognition.")
        text = ''
        with sr.Microphone() as source:
            while True:
                try:
                    audio = r.listen(source,phrase_time_limit=3) # listen to source
                    # use testing api key
                    text = r.recognize_google(audio, language="vi-VN").lower()
                    print("Voice: ", text)
                    if  text.find('tắt đèn') != -1:
                        self.signalVoice.put(0)#tắt đèn 
                    elif text.find('chế độ sinh hoạt') != -1:
                        self.signalVoice.put(1)#tắt camera
                    elif text.find('chế độ nhiệt độ') != -1:
                        self.signalVoice.put(2)
                    elif text.find('chế độ chống trộm') != -1:
                        self.signalVoice.put(3)
                    elif text.find('an toàn') !=-1:
                        self.signalVoice.put(4)
                    else:
                        self.signalVoice.put(5)
                    self.voice_text.put(text)
                    self.voice_time.put(datetime.now())
                except sr.UnknownValueError:
                    print("Voice: No signal")
                    self.signalVoice.put(5)#no signal
                    self.voice_text.put("No Signal")
                    self.voice_time.put(datetime.now())
                except sr.RequestError:
                    print("API call failed. Key valid? Internet connection?")

                time.sleep(0.5)

                if not self.voice_destroy.empty(): 
                    break

class TemperatureProcess(multiprocessing.Process):
    def __init__(self, temperature, tmp_destroy, web_state, web_time):
        multiprocessing.Process.__init__(self)
        self.temperature = temperature
        self.tmp_destroy = tmp_destroy
        self.web_state = web_state
        self.web_time = web_time

    def run(self):
        s = socket.socket()         
        s.bind(('0.0.0.0', 8090 ))
        s.listen(0)                 
        
        while True:
            client, addr = s.accept()
            if not self.tmp_destroy.empty():
                print("Closing connection")
                client.close()
                break
            while True:
                content = client.recv(32)
                if len(content) == 0:
                    break
                else:
                    content_str = content.decode('utf-8')
                    tmp = int(content_str)
                    temp = tmp//10
                    self.temperature.put(temp)
                    state = int(tmp%10 - 1)
                    if state != -1:
                        self.web_state.put(state)
                    self.web_time.put(datetime.now())
                    #print("------------- ", temp, " --- ",state)
                time.sleep(0.5)
            time.sleep(0.5)
        
class MainWindow:
    def __init__(self, root, sendFrame, signalCam, signalVoice, voice_time, button_time, buttonState, cam_destroy, voice_destroy, voice_text, signal_safe, temperature, tmp_destroy, web_state, web_time):
        self.root = root
        self.root.title("Multiprocessing Program")
        self.text = "No signal"  # voice
        self.style = ThemedStyle(self.root)
        self.style.set_theme("arc")  

        self.custom_font = ('Helvetica', 12)

        self.style.configure("TLabel", font=self.custom_font)

        self.style.configure("TButton", font=self.custom_font)

        # Set the style for frames
        self.style.configure("TFrame", font=self.custom_font)

        self.video_label = tk.Label(root)
        self.video_label.grid(row=0, column=0, columnspan=4, padx=10, pady=10)  # Span across all columns

        # arduino
        self.arduino = SerialObject("COM5")

        # signals
        self.signalCam = signalCam
        self.sendFrame = sendFrame
        self.signalVoice = signalVoice
        self.buttonState = buttonState
        self.cam_destroy = cam_destroy
        self.voice_destroy = voice_destroy
        self.voice_text = voice_text
        self.signal_safe = signal_safe
        self.temperature = temperature
        self.tmp_destroy = tmp_destroy
        self.web_state = web_state
        self.web_time = web_time
        # signal of time
        self.voice_time = voice_time
        self.button_time = button_time

        # camera, voice và nhiệt độ
        self.video_process = VideoProcess(sendFrame=self.sendFrame, signalCam=self.signalCam, check_destroy=cam_destroy, signal_safe=self.signal_safe)
        self.audio_process = AudioProcess(signalVoice=self.signalVoice, voice_time=self.voice_time, voice_destroy=self.voice_destroy, voice_text=self.voice_text)
        self.temperature_process = TemperatureProcess(temperature=self.temperature,tmp_destroy=self.tmp_destroy, web_state=self.web_state, web_time=self.web_time)

        self.video_process.start()
        self.audio_process.start()
        self.temperature_process.start()

        self.canvas = tk.Canvas(root)
        self.canvas.grid(row=1, column=0, columnspan=4, padx=10, pady=10)  # Span across all columns

        # tắt đèn
        self.turn_off_light = ttk.Button(root, text="Tắt đèn", command=lambda: self.updateStateByButton(0))
        self.turn_off_light.grid(row=2, column=0, padx=10, pady=10)

        # bật đèn
        self.turn_on_light = ttk.Button(root, text="Đèn bình thường", command=lambda: self.updateStateByButton(1))
        self.turn_on_light.grid(row=2, column=1, padx=10, pady=10)

        # đèn theo nhiệt độ
        self.turn_on_light = ttk.Button(root, text="Đèn nhiệt độ", command=lambda: self.updateStateByButton(2))
        self.turn_on_light.grid(row=2, column=2, padx=10, pady=10)

        # bật tính năng an toàn
        self.safe_button = ttk.Button(root, text="Cảnh báo an toàn", command=lambda: self.updateStateByButton(3))
        self.safe_button.grid(row=2, column=3, padx=10, pady=10)

        #button để gửi tín hiệu an toàn cho camera
        self.safe_signal_button = ttk.Button(root, text="Xác nhận an toàn", command=self.sendSignalSafe)
        self.safe_signal_button.grid(row=3, column=0, padx=10, pady=10)

        # Tạo button để thoát chương trình
        self.quit_button = ttk.Button(root, text="Thoát", command=self.quit)
        self.quit_button.grid(row=3, column=1, padx=10, pady=10)

        # nội dung của voice
        self.voice_label = tk.Label(self.root, text="Voice: ", font=self.custom_font)
        self.voice_label.grid(row=3, column=2, padx=10, pady=5, sticky='e')

        self.value_voice_label = tk.Label(self.root, text=self.text, font=self.custom_font)
        self.value_voice_label.grid(row=3, column=3, columnspan=3, padx=10, pady=5, sticky='w') 

        self.displayCam()
        self.sendSignalForDevice()
        self.displayVoiceText()

    def sendSignalSafe(self):
        self.signal_safe.put(1)

    def updateStateByButton(self, type):
        if type != 3:
            self.signal_safe.put(0)
        else:
            self.signal_safe.put(1)
        self.buttonState.put(type)
        self.button_time.put(datetime.now())
        
    def displayVoiceText(self):
        if not self.voice_text.empty():
            self.text = self.voice_text.get()
        else:
            self.text = "No Voice"
        self.value_voice_label.config(text=self.text)

        # Lặp lại hàm update sau một khoảng thời gian nhất định
        self.root.after(2000, self.displayVoiceText)

    def displayCam(self):
        if not self.sendFrame.empty() :
            frame = self.sendFrame.get()
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(image)
            photo = ImageTk.PhotoImage(image=image)

            # Hiển thị hình ảnh trên canvas
            self.canvas.config(width=photo.width(), height=photo.height())
            self.canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            self.canvas.image = photo
        
        # Lặp lại hàm update sau 10 milliseconds
        self.root.after(10, self.displayCam)
    
    def sendSignalForDevice(self):
        res_cam = [3,3]
        if not self.signalCam.empty():
            res_cam = self.signalCam.get()
        #voice phải lấy lần cuối cùng để so sánh    
        voice_time = None
        while not self.voice_time.empty():
            voice_time = self.voice_time.get()

        signalVoice = None
        while not self.signalVoice.empty():
            signalVoice = self.signalVoice.get()

        #button
        button_time = None
        while not self.button_time.empty():
            button_time = self.button_time.get()

        signalButton = None
        while not self.buttonState.empty():
            signalButton = self.buttonState.get()

        #nhiệt độ
        temp = None
        while not self.temperature.empty():
            temp = self.temperature.get()
        if temp is None:
            temp = 50
        
        #yêu cầu từ website
        w_time = None
        while not self.web_time.empty():
            w_time = self.web_time.get()

        w_state = None
        while not self.web_state.empty():
            w_state = self.web_state.get()

        latest_time = None
        data = 5

        if voice_time is not None:
            latest_time = voice_time
            data = signalVoice

        if button_time is not None and (latest_time is None or button_time > latest_time):
            latest_time = button_time
            data = signalButton

        if w_time is not None and (latest_time is None or w_time > latest_time):
            latest_time = w_time
            data = w_state
        
        if data == 4:
            data = 5
            self.signal_safe.put(1)
        elif data == 3:
            self.signal_safe.put(1)
        elif data == None:
            data = 5
        elif data != 5:
            self.signal_safe.put(0)

        signalForArduino = [data,res_cam[0],res_cam[1], temp]
        if data != 5:
            print("--------------------", signalForArduino)
        elif res_cam[0] == 0:
            print("--------------------", signalForArduino)
        self.arduino.sendData(signalForArduino)
        self.root.after(10, self.sendSignalForDevice)

    def quit(self):
        # Dừng camera, voice và đóng cửa sổ
        self.cam_destroy.put(1)
        self.voice_destroy.put(1)
        self.tmp_destroy.put(1)
        self.root.destroy()

if __name__ == "__main__":
    signalCam = multiprocessing.Queue()
    sendFrame = multiprocessing.Queue()
    signalVoice = multiprocessing.Queue()
    voice_time = multiprocessing.Queue()
    button_time = multiprocessing.Queue()
    buttonState = multiprocessing.Queue()
    cam_destroy = multiprocessing.Queue()
    voice_destroy = multiprocessing.Queue()
    voice_text = multiprocessing.Queue()
    signal_safe = multiprocessing.Queue()
    temperature = multiprocessing.Queue()
    tmp_destroy = multiprocessing.Queue()
    web_state = multiprocessing.Queue()
    web_time = multiprocessing.Queue()
    root = tk.Tk()
    app = MainWindow(root, sendFrame, signalCam, signalVoice, voice_time, button_time, buttonState, cam_destroy, voice_destroy, voice_text, signal_safe, temperature, tmp_destroy,web_state,web_time)
    root.mainloop()
          

import cv2
import threading
from queue import Queue
import time
from typing import Tuple
import mediapipe as mp
import tkinter as tk
import tkinter.messagebox
from PIL import Image, ImageTk

_face_detection = mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.5)


class FaceDetectionThread:
    def __init__(self, freq: float = 2, camera_index: int = 0):
        self._freq = 1 / freq
        self._capture = cv2.VideoCapture(0)
        self._result_queue = Queue()  # [(now, face num), ...]
        self._run_flag = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        # with self._face_detection:
        while self._run_flag and self._capture.isOpened():
            success, image = self._capture.read()
            if not success:
                continue

            # Flip the image horizontally for a later selfie-view display, and convert
            # the BGR image to RGB.
            image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
            # To improve performance, optionally mark the image as not writeable to
            # pass by reference.
            image.flags.writeable = False
            results = _face_detection.process(image)

            image.flags.writeable = True
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            if results.detections:
                for detection in results.detections:
                    mp.solutions.drawing_utils.draw_detection(image, detection)
            self._result_queue.put(
                (time.time(), len(results.detections) if results.detections else 0, image))
            time.sleep(self._freq)

    def get_result(self) -> Tuple[float, int]:
        if not self._thread.is_alive():
            return None
        return self._result_queue.get()

    def clear_queue(self):
        while not self._result_queue.empty():
            self._result_queue.get()

    def start(self):
        self._run_flag = True
        self._thread.start()

    def close(self):
        self._run_flag = False
        if self._thread.is_alive():
            self._thread.join()
        self._capture.release()

    def __enter__(self) -> "FaceDetectionThread":
        self.start()
        return self

    def __exit__(self, *args, **kargv):
        self.close()


default_img = Image.new('RGBA', (400, 400), "gray")


class SittingTime:
    tremble = 3  # if sitting time > 3s , time accumulation

    def __init__(self):
        self._total_sit_time = 0
        self._now_sit_time = 0
        self._total_leave_time = 0
        self._now_leave_time = 0
        self._last_leave_timestamp = -1
        self._last_sit_timestamp = -1
        self._last_sit_state = None

    def put_data(self, timestamp: float, state: bool):
        """
        calculate sitting total time
        state(bool): True ->sitting  False ->no sitting
        """
        if self._last_sit_state is None:  # init
            if state:
                self._last_sit_timestamp = timestamp
            else:
                self._last_leave_timestamp = timestamp
            self._last_sit_state = state
            return
        if self._last_sit_state == state:
            if state:
                self._now_sit_time += timestamp - self._last_sit_timestamp
                self._last_sit_timestamp = timestamp
                if self._now_sit_time > self.tremble:
                    self._total_sit_time += self._now_sit_time
                    self._now_sit_time = 0
            else:
                self._now_leave_time += timestamp - self._last_leave_timestamp
                self._last_leave_timestamp = timestamp
                if self._now_leave_time > self.tremble:
                    self._total_leave_time += self._now_leave_time
                    self._now_leave_time = 0
        else:
            if state:
                self._last_sit_timestamp = timestamp
                if self._now_leave_time < self.tremble:
                    self._now_leave_time = 0
            else:
                self._last_leave_timestamp = timestamp
                if self._now_sit_time < self.tremble:
                    self._now_sit_time = 0
            self._last_sit_state = state

    def get_sit_time(self) -> float:
        return self._total_sit_time

    def get_leave_time(self) -> float:
        return self._total_leave_time

    def clear(self):
        self._total_sit_time = 0
        self._now_sit_time = 0
        # adopting mandatory pop-up window in extra functional,the pop-up time exceeds the total departure time
        self._total_leave_time = 0
        self._now_leave_time = 0
        self._last_leave_timestamp = -1

        self._last_sit_timestamp = -1
        # true or false (true is sitting ,flase is no sitting)
        self._last_sit_state = None


class MainForm(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self._run_flag = False
        self._runner = None
        self.create_widgets()
        self.pack(expand=tk.YES, fill=tk.BOTH)

    def create_widgets(self):
        # self._set_ttk_style()
        self._frame_menu = tk.Frame(self)
        self._frame_menu.pack(side=tk.TOP)

        # FPS input box
        # _frame_temp = tk.Frame(self._frame_menu)
        # _frame_temp.pack(side=tk.TOP)
        # _label_temp = tk.Label(_frame_temp, text="CAMERA FPS: ")
        # _label_temp.pack(side=tk.LEFT)
        # self._strvar_fps = tk.StringVar(value="20")
        # self._entry_fps = tk.Entry(_frame_temp, text=self._strvar_fps, width=8)
        # self._entry_fps['text'] = '10'
        # self._entry_fps.pack(side=tk.LEFT)
        # Camera input box
        # _frame_temp = tk.Frame(self._frame_menu)
        # _frame_temp.pack(side=tk.TOP)
        # _label_temp = tk.Label(_frame_temp, text="CAMERA IDX: ")
        # _label_temp.pack(side=tk.LEFT)
        # self._strvar_camidx = tk.StringVar(value="0")
        # self._entry_camera_index = tk.Entry(_frame_temp, text=self._strvar_camidx, width=8)
        # self._entry_camera_index.pack(side=tk.LEFT)

        # sit warn time
        _frame_temp = tk.Frame(self._frame_menu)
        _frame_temp.pack(side=tk.TOP)
        _label_temp = tk.Label(_frame_temp, text="Sitting Time:")
        _label_temp.pack(side=tk.LEFT)
        self._strvar_sit_time = tk.StringVar(value="30")
        self._entry_sit_time = tk.Entry(_frame_temp, text=self._strvar_sit_time, width=8)
        self._entry_sit_time.pack(side=tk.LEFT)
        _label_temp = tk.Label(_frame_temp, text="min")
        _label_temp.pack(side=tk.LEFT)

        # START Button
        _frame_temp = tk.Frame(self._frame_menu)
        _frame_temp.pack(side=tk.TOP)
        self._start_btn = tk.Button(_frame_temp, text='START', command=self._start_btn_click)
        self._start_btn.pack(side=tk.LEFT)

        # people info
        _frame_temp = tk.Frame(self._frame_menu)
        _frame_temp.pack(side=tk.TOP)

        _frame_temp_t = tk.Frame(_frame_temp)
        _frame_temp_t.pack(side=tk.TOP)
        _temp_labe = tk.Label(_frame_temp_t, text="Face Count:")
        _temp_labe.pack(side=tk.LEFT)
        # people face number
        self._label_people = tk.Label(_frame_temp_t, text="0")
        self._label_people.pack(side=tk.LEFT)

        _frame_temp_t = tk.Frame(_frame_temp)
        _frame_temp_t.pack(side=tk.TOP)
        _temp_labe = tk.Label(_frame_temp_t, text="Sitting Time:")
        _temp_labe.pack(side=tk.LEFT)
        # total sitting time
        self._label_sit = tk.Label(_frame_temp_t, text="0.00s")
        self._label_sit.pack(side=tk.LEFT)

        _frame_temp_t = tk.Frame(_frame_temp)
        _frame_temp_t.pack(side=tk.TOP)
        _temp_labe = tk.Label(_frame_temp_t, text="  Leave Time:")
        _temp_labe.pack(side=tk.LEFT)
        # total leave time
        self._label_leave = tk.Label(_frame_temp_t, text="0.00s")
        self._label_leave.pack(side=tk.LEFT)

        # screen label
        self._camera_view = ImageTk.PhotoImage(default_img)
        self._label = tk.Label(self, image=self._camera_view)
        self._label.pack(side=tk.TOP, fill=tk.NONE, expand='no', anchor=tk.NW)

    def _start_btn_click(self):
        if self._start_btn['text'] == "START":
            self._run_flag = True
            self._runner = threading.Thread(target=self._run_show_image, daemon=True)
            self._runner.start()
            self._start_btn['text'] = "STOP"
        else:
            self._start_btn['text'] = "START"
            self._run_flag = False
            self._runner = None

    def _run_show_image(self):
        sss = SittingTime()
        # fps = int(self._strvar_fps.get())
        # cam_idx = int(self._strvar_camidx.get())
        fps = 20
        cam_idx = 0
        sit_top = float(self._strvar_sit_time.get())

        with FaceDetectionThread(freq=fps, camera_index=cam_idx) as face_detection:
            while self._run_flag:
                result = face_detection.get_result()
                if result:
                    # def refresh(img):
                    timestamp, face_count, img = result
                    # print(f'{t} {c}')
                    sss.put_data(timestamp, face_count > 0)
                    self._label_people['text'] = str(face_count)
                    img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).resize((400, 400))
                    self._camera_view.paste(img)
                    self._label_sit['text'] = "%.2fs" % sss.get_sit_time()
                    self._label_leave['text'] = "%.2fs" % sss.get_leave_time()
                    if sss.get_sit_time() > sit_top * 60:
                        tkinter.messagebox.askquestion(title='Hi', message='Please stand up and have a rest')
                        face_detection.clear_queue()
                        sss.clear()
        self._camera_view.paste(default_img)


def main():
    m = MainForm()
    m.mainloop()


if __name__ == '__main__':
    main()

import time
import cv2
from cv2 import VideoCapture, imwrite
import os
import datetime

if __name__ == "__main__":

    sleep_tm = 2
    
    cam = VideoCapture(0)

    prev_gray = None
    run = True
    motion_dir = None

    last_event_ts = None

    motion_timeout = 7

    while run:

        event_ts = datetime.datetime.now()
        
        result, image = cam.read()

        hist = cv2.calcHist([image], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        hist = cv2.normalize(hist, hist).flatten()
                
        ts_now = event_ts.strftime('%Y-%m-%d_%H-%M-%S')

        d = cv2.compareHist(hist, prev_gray, cv2.HISTCMP_CORREL) if prev_gray is not None else 0

        if d < 0.9:

            event_duration = (event_ts - last_event_ts).total_seconds() if last_event_ts else 0

            if motion_dir is None or event_duration > motion_timeout:
                
                motion_dir = f"motions/motion_{ts_now}"
                print(f"Starting new event: {motion_dir}. Time since last motion: {event_duration}")

                os.makedirs(motion_dir)
            
            last_event_ts = event_ts

            motion_path = f"{motion_dir}/event_{ts_now}.png"
            imwrite(motion_path, image)
            imwrite(f"motions/event_current.png", image)

            print(f"Motion recorded to: {motion_path}")

        imwrite(f"motions/current_frame.png", image)
        prev_gray = hist

        print(f"Sleeping for {sleep_tm} seconds")
        time.sleep(sleep_tm)
    
    cam.release()

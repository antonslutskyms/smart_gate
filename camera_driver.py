import time
import cv2
from cv2 import VideoCapture, imwrite
import os
import datetime
import io
import json

from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials

subscription_key = os.getenv("VISION_KEY")
endpoint = os.getenv("VISION_ENDPOINT")

computervision_client = ComputerVisionClient(endpoint, CognitiveServicesCredentials(subscription_key))

if __name__ == "__main__":

    sleep_tm = 0.5

    cam = VideoCapture(0)

    prev_gray = None
    run = True
    motion_dir = None

    last_event_ts = None

    motion_timeout = 7

    SUPPORTED_OBJECTS = ["mammal", "cat", "animal", "person"]

    while run:

        event_ts = datetime.datetime.now()

        result, image = cam.read()

        hist = cv2.calcHist([image], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        hist = cv2.normalize(hist, hist).flatten()

        ts_now = event_ts.strftime('%Y-%m-%d_%H-%M-%S')

        d = cv2.compareHist(hist, prev_gray, cv2.HISTCMP_CORREL) if prev_gray is not None else 0

        if d < 0.997:

            is_success, buffer = cv2.imencode(".jpg", image)
            io_buf = io.BytesIO(buffer)
            
            vision_response = computervision_client.detect_objects_in_stream(io_buf)

            print(f"\nObjects analysis [{ts_now}]:")
            
            supported_found = False
            
            found_objects = []

            for object in vision_response.objects:
                print(object.object_property, object.confidence)
                found_objects.append({
                    "object_property" : object.object_property,
                    "confidence" : object.confidence
                })
                
                if object.object_property in SUPPORTED_OBJECTS and not supported_found and object.confidence > 0.7:
                    supported_found = True
                    print(f"Found supported object: {object.object_property}")

            info_obj = {
                    "event_ts" : ts_now,
                    "distance" : d,
                    "objects" : found_objects
                }

            with open("motions/latest_info.json", "w") as latest_info_json:
                latest_info_json.write(json.dumps(info_obj))

            if supported_found:
                
                event_duration = (event_ts - last_event_ts).total_seconds() if last_event_ts else 0

                if motion_dir is None or event_duration > motion_timeout:

                    motion_dir = f"motions/motion_{ts_now}"
                    info_dir = f"infos/info_{ts_now}"
                    
                    print(f"Starting new event[{d}]: {motion_dir}. Time since last motion: {event_duration}")

                    os.makedirs(motion_dir)
                    os.makedirs(info_dir)

                last_event_ts = event_ts

                motion_path = f"{motion_dir}/event_{ts_now}.png"
                imwrite(motion_path, image)

                info_path = f"{info_dir}/info_{ts_now}.json"
                with open(info_path, "w") as info_json:
                    info_json.write(json.dumps(info_obj))


                imwrite(f"motions/event_current.png", image)

                print(f"Motion recorded to: {motion_path}")
            else:
                print(f"Ignoring [{ts_now}]")

            
        
        imwrite(f"motions/current_frame.png", image)
        prev_gray = hist

#        print(f"Sleeping for {sleep_tm} seconds. Last distance: {d}")
        time.sleep(sleep_tm)

    cam.release()

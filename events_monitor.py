import time

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
import os
import threading
import time

import run_smart_gate as rsg


def process_event(self, src_path):
    self.lock.acquire()

    try:
        
        if src_path not in self.event_threads:
        
            try:
                os.system("aplay -D sysdefault:CARD=Headphones event_detected.wav")
            except:
                print("WARNING: Unable to play sound")

            self.event_threads.append(src_path)

            print(f"Processing event: {src_path} events: {self.event_threads}")
            time.sleep(5)
            print("Checking dir:", src_path)
            
            data_actions = []

            events_root_dir = src_path


            for filename in os.listdir(events_root_dir):
                file_path = os.path.join(events_root_dir, filename)
                if os.path.isfile(file_path):
                    data_actions.append({"type": "image", "path": filename})

            print("Data Actions: ", data_actions)

            prompt, image_urls = rsg.render_prompt(data_actions, images_root_dir = events_root_dir)

            print(f"---- Prompt:\n{prompt}\n----")

            lm_response = rsg.llm_task(user_prompt = prompt, 
                    system_prompt="What do you see in the pictures?", 
                    image_urls = image_urls)

            print(f"==== Response:\n{lm_response}\n====")

            self.event_threads.remove(src_path)
            print(f"Releasing thread: {src_path}")

        else:
            print("Race condition")
        
    except:
        print("ERROR: Event processing failed", sys.exc_info()[0])
    finally:
        self.lock.release()



class EventHandler(FileSystemEventHandler):
    def __init__(self):
        self.event_threads = []
        self.lock = threading.Lock()




    def on_any_event(self, event: FileSystemEvent) -> None:

        if os.path.isdir(event.src_path) and "motion_" in event.src_path and len(self.event_threads) == 0:                
            
                print(f"Detected event: {event.src_path} ..............")
                event_thread = threading.Thread(target = process_event, args = (self, event.src_path,))
                event_thread.start()
            # else:
            #     print(f"Event dropped: {event.src_path} ..............")

        


event_handler = EventHandler()
observer = Observer()
observer.schedule(event_handler, "./motions", recursive=True)
observer.start()
try:
    while True:
        time.sleep(1)
finally:
    observer.stop()
    observer.join()
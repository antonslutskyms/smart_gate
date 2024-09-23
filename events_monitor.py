import time

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
import os
import sys
import threading
import time
import json

import run_smart_gate as rsg

from jinja2 import Environment, FileSystemLoader

env = Environment(loader = FileSystemLoader('templates'))
event_analysis_prompt_template = env.get_template('event_analysis_prompt.jinja')

def play_sound(file = "event_detected.wav"):
    try:
        os.system(f"aplay -D sysdefault:CARD=Headphones {file}")
    except:
        print("WARNING: Unable to play sound")

def gate_open():
    try:
        os.system(f"python3.10 servo3.py 30")
    except:
        print("WARNING: Unable to open gate")

def gate_close():
    try:
        os.system(f"python3.10 servo3.py 180")
    except:
        print("WARNING: Unable to close gate")

def maybe_act_on_llm_response(llm_response):
    try:
        print("Processing LLM response:", llm_response)

        json_response = json.loads(llm_response)

        if json_response["allowed"] == "Yes":
            play_sound("yes.wav")
        elif json_response["allowed"] == "No":
            play_sound("no.wav")
            gate_open()
        else:
            print("WARNING: JSON object not supported:", json_response)
        
    except:
        print(f"ERROR: LLM response not understood:\n---------------------------------------\n{llm_response}\n---------------------------------------", sys.exc_info()[0])



def process_event(self, src_path):
    #print(src_path)
    
    self.lock.acquire()

#    try:
    if True:
        
        if src_path not in self.event_threads:
        
            play_sound()
            gate_close()

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

            event_analysis_prompt = event_analysis_prompt_template.render()

            print(f"---- System Prompt:\n{event_analysis_prompt}\n----")

            print(f"---- User Prompt:\n{prompt}\n----")

            llm_response = rsg.llm_task(user_prompt = prompt, 
                    system_prompt=event_analysis_prompt, 
                    image_urls = image_urls)

            print(f"==== Response:\n{llm_response}\n====")

            maybe_act_on_llm_response(llm_response)
            print("Sleeping for time to skip subsequent events")
            time.sleep(25)
            print("Getting more events")
        else:
            print("Race condition")
        
    # except:
    #     print("ERROR: Event processing failed", sys.exc_info()[0])
    # finally:
        self.event_threads.remove(src_path)
        print(f"Releasing thread: {src_path}")
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
        else:
            print(f"Event dropped: {event.src_path} ..............")

        


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
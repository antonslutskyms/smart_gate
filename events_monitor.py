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

filter_images_template = env.get_template('filter_images_template.jinja')
event_analysis_prompt_template = env.get_template('event_analysis_prompt.jinja')


def say_it(text):
    try:
        os.system(f"espeak -g 3 -s 120 '{text}' 2> /dev/null")
    except:
        print("WARNING: Unable to play sound")

def play_sound(file = "event_detected.wav"):
    try:
        os.system(f"aplay -D sysdefault:CARD=Headphones {file} 2> /dev/null")
    except:
        print("WARNING: Unable to play sound")

def gate_open():
    try:
        print("ATTENTION: GATE OPENING")
        os.system(f"python3.10 servo3.py 20")
    except:
        print("WARNING: Unable to open gate")

def gate_close():
    try:
        print("ATTENTION: GATE CLOSING")
        os.system(f"python3.10 servo3.py 170")
    except:
        print("WARNING: Unable to close gate")

def maybe_act_on_llm_response(llm_response):
    try:
        print("Processing LLM response:", llm_response)

        json_response = json.loads(llm_response)

        if json_response["has_object"] == "Yes":
            #play_sound("yes.wav")
            say_it("Rodents detected.")
        elif json_response["has_object"] == "No":
            #play_sound("no.wav")
            gate_open()
            say_it("Rodents not detected.")
            
        else:
            print("WARNING: JSON object not supported:", json_response)
        
    except:
        print(f"ERROR: LLM response not understood:\n---------------------------------------\n{llm_response}\n---------------------------------------", sys.exc_info()[0])


def llm_analyze_event_images(system_prompt, events_root_dir):

    data_actions = []

    dir_list = os.listdir(events_root_dir)

    say_it(f"Analyzing {len(dir_list)} images.")            

    for filename in dir_list:
        file_path = os.path.join(events_root_dir, filename)
        if os.path.isfile(file_path):
            data_actions.append({"type": "image", "path": filename})

    print("Data Actions: ", data_actions)

    prompt, image_urls = rsg.render_prompt(data_actions, images_root_dir = events_root_dir)

    print(f"---- System Prompt:\n{system_prompt}\n----")

    print(f"---- User Prompt:\n{prompt}\n----")

    return rsg.llm_task(user_prompt = prompt, 
            system_prompt=system_prompt, 
            image_urls = image_urls)


def process_event(self, src_path):
    #print(src_path)
    
    self.lock.acquire()

#    try:
    if True:
        
        if src_path not in self.event_threads:
        
            say_it("Event detected.")
            #play_sound()
            gate_close()

            self.event_threads.append(src_path)

            say_it("Waiting for event to populate.")
            print(f"Processing event: {src_path} events: {self.event_threads}")
            time.sleep(5)


            print("Checking dir:", src_path)

            events_root_dir = src_path

            images_filter = None
            try:
                analysis_prompt = filter_images_template.render()
                llm_response = llm_analyze_event_images(analysis_prompt, events_root_dir)
                print(f"[IMAGE FILTER] LLM Response:\n{llm_response}")

                images_filter = json.loads(llm_response)

                best_pic_str = " ".join([str(i) for i in images_filter])

                say_it(f"Best pics are {best_pic_str} images.")

                print(f"[IMAGE FILTER] filter: {images_filter}")
            except:
                print("WARNING: Failed to get filtered images!", sys.exc_info()[0])
                say_it("Warning! Error filtering images.")

            if images_filter:
                
                data_actions = []

                i = 0
                for filename in os.listdir(events_root_dir):
                    file_path = os.path.join(events_root_dir, filename)
                    if os.path.isfile(file_path):
                        if not images_filter or i in images_filter:
                            data_actions.append({"type": "image", "path": filename})
                        i += 1 

                print("Data Actions: ", data_actions)

                prompt, image_urls = rsg.render_prompt(data_actions, images_root_dir = events_root_dir)

                event_analysis_prompt = event_analysis_prompt_template.render()

                print(f"---- System Prompt:\n{event_analysis_prompt}\n----")

                print(f"---- User Prompt:\n{prompt}\n----")

                llm_response = rsg.llm_task(user_prompt = prompt, 
                        system_prompt=event_analysis_prompt, 
                        image_urls = image_urls)

                print(f"==== Response:\n{llm_response}\n====")

                llm_response_descr = rsg.llm_task(user_prompt = prompt, 
                        system_prompt="How many images do you see?  Describe each image.", 
                        image_urls = image_urls)

                #say_it(llm_response_descr)

                maybe_act_on_llm_response(llm_response)

                # Persisting llm results:
                info_path = src_path.replace("motions", "infos").replace("motion_", "info_")
                info_path = info_path +"/data_actions.json"

                open(info_path, "w").write(json.dumps({"data_actions" : data_actions,
                                                        "images_description" : llm_response_descr,
                                                        }))

                print("\n\n----------------- Sleeping for time to skip subsequent events ------------\n\n")
                
                gate_open_timeout = 60
                
                say_it(f"Gate will be open for {gate_open_timeout} seconds.")
                
                step = 5

                for i in range(1, gate_open_timeout, step): 
                    time.sleep(step)
                    say_it(f"{gate_open_timeout - i}")
                
                say_it("Gate may close now.")
                print("Getting more events")
            else:
                say_it("Not enough clear images.")
                print("Not enough clear images")
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

        if os.path.isdir(event.src_path):
            if "motion_" in event.src_path and len(self.event_threads) == 0:                
                
                print(f"Detected event: {event.src_path} ..............")
                event_thread = threading.Thread(target = process_event, args = (self, event.src_path,))
                event_thread.start()
            elif event.src_path != "./motions":
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
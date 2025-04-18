import time

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
import os
import sys
import threading
import time
import json
import datetime

import run_smart_gate as rsg

from jinja2 import Environment, FileSystemLoader

env = Environment(loader = FileSystemLoader('templates'))

filter_images_template = env.get_template('filter_images_template.jinja')
event_analysis_prompt_template = env.get_template('event_analysis_prompt.jinja')

ignore_events_timeout = 60*3
min_num_pics = 100


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

def color_toggle(color, on_off):
    try:
        print("ATTENTION: COLOR CHANGING", color, on_off)
        os.system(f"python3.10 {color}_{on_off}.py")
    except:
        print("WARNING: Unable to open gate")

def gate_open():
    threading.Thread(target = _gate_open).start()

def _gate_open():
    try:
        print("ATTENTION: GATE OPENING")
        color_toggle("red", "off")
        color_toggle("green", "on")
        os.system(f"python3.10 servo3.py 20")
    except:
        print("WARNING: Unable to open gate")

def gate_close():
    threading.Thread(target = _gate_close).start()

def _gate_close():
    try:
        print("ATTENTION: GATE CLOSING")
        color_toggle("green", "off")
        color_toggle("red", "on")

        os.system(f"python3.10 servo3.py 170")
    except:
        print("WARNING: Unable to close gate")

def maybe_act_on_llm_response(llm_response):
    try:
        print("Processing LLM response:", llm_response)

        json_response = json.loads(llm_response)

        if json_response["has_object"] == "Yes":
            #play_sound("yes.wav")
            return False
        elif json_response["has_object"] == "No":
            #play_sound("no.wav")
            gate_open()
            gate_open()
            return True
            
        else:
            print("WARNING: JSON object not supported:", json_response)
        
    except:
        print(f"ERROR: LLM response not understood:\n---------------------------------------\n{llm_response}\n---------------------------------------", sys.exc_info()[0])

    return False

def llm_analyze_event_images(system_prompt, events_root_dir):

    data_actions = []

    dir_list = os.listdir(events_root_dir)

    print(f"Analyzing {len(dir_list)} images.")
    #say_it(f"Analyzing {len(dir_list)} images.")            

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
    
    #self.lock.acquire()

#    try:
    if True:
        
        if src_path not in self.event_threads:

            info_path = src_path.replace("motions", "infos").replace("motion_", "info_")
            info_path = info_path +"/data_actions.json"

            #say_it
            
            print(f"\n================ Recieved new event: {src_path}")
            self.last_process_started = datetime.datetime.now()
            #play_sound()
            gate_close()
            gate_close()
            gate_close()

            self.event_threads.append(src_path)

            #say_it
            print("Waiting for event to populate.")
            print(f"Processing event: {src_path} events: {self.event_threads}")

            t = 15
            print("Observing gate for....")      
            
            event_data_collection_start = datetime.datetime.now()  
            
            for i in range(t):
                print(f"{i} of {t} s")

                
                color_toggle("red", "on")
                time.sleep(1)
                color_toggle("red", "off")

                num_pics = len(os.listdir(src_path))
                print(f"Checking dir: {src_path} | Num Pics: {num_pics}")
                if num_pics >= min_num_pics:
                    print("Mimimum pics detected")
                    break
                

            for i in range(3):
                color_toggle("red", "on")
                color_toggle("red", "off")
            
            event_process_start_ts = datetime.datetime.now()
            
            event_data_collection_time = (event_process_start_ts - event_data_collection_start).total_seconds()

            events_root_dir = src_path
            
            events_root_dir_list = os.listdir(events_root_dir)

            images_filter = [i for i in range(len(events_root_dir_list))]

            llm_filtering_time = -1

            image_filter_prompt = None

            if True:

                
                analysis_prompt = filter_images_template.render()
                image_filter_prompt = analysis_prompt

                llm_response, llm_filtering_time = llm_analyze_event_images(analysis_prompt, events_root_dir)
                print(f"[IMAGE FILTER] LLM Response:\n{llm_response}")

                try:
                    images_filter = json.loads(llm_response)

                    best_pic_str = " ".join([str(i) for i in images_filter])

                    print(f"Best pics are {best_pic_str} images.")

                    print(f"[IMAGE FILTER] filter: {images_filter}")

                    print(f"DATA: Filter {llm_filtering_time} seconds.")
                except:
                    print("Filter LLM response not understood: ", llm_response)

            if images_filter:
                
                data_actions = []

                all_data_actions = []

                i = 0
                for filename in os.listdir(events_root_dir):
                    file_path = os.path.join(events_root_dir, filename)
                    if os.path.isfile(file_path):
                        data_action = {"type": "image", "path": filename}
                        if not images_filter or i in images_filter:
                            data_actions.append(data_action)
                        all_data_actions.append(data_action)
                        i += 1 

                print("Data Actions: ", data_actions)

                prompt, image_urls = rsg.render_prompt(data_actions, images_root_dir = events_root_dir)

                event_analysis_prompt = event_analysis_prompt_template.render()

                print(f"---- System Prompt:\n{event_analysis_prompt}\n----")

                print(f"---- User Prompt:\n{prompt}\n----")

                llm_response, llm_response_time = rsg.llm_task(user_prompt = prompt, 
                        system_prompt=event_analysis_prompt, 
                        image_urls = image_urls)

                print(f"==== Response:\n{llm_response}\n====")

                #say_it(llm_response_descr)

                time_to_action = (datetime.datetime.now() - event_data_collection_start).total_seconds()

                print("_____________________________________________________________________________________________")
                print(f"__________ TIME TO ACTION: {time_to_action} seconds. __________")
                print("_____________________________________________________________________________________________")

                is_gate_open = maybe_act_on_llm_response(llm_response)

                # Persisting llm results:


                response_info = { "unfiltered_data_actions" : all_data_actions, 
                                                        "filtered_data_actions" : data_actions,
                                                        "llm_response" : llm_response,
                                                        "is_gate_open" : is_gate_open,
                                                        "time_to_action" : time_to_action,
                                                        "llm_filtering_time" : llm_filtering_time,
                                                        "llm_response_time" : llm_response_time,
                                                        "event_data_collection_time" : event_data_collection_time,
                                                        "image_filter_prompt" : image_filter_prompt,
                                                        "event_analysis_prompt" : event_analysis_prompt

                                                        }

                print(f"-------- Response Info:\n{response_info}\n---------")

                open(info_path, "w").write(json.dumps(response_info))

                print("\n\n----------------- Sleeping for time to skip subsequent events ------------\n\n")
                
                gate_open_timeout = ignore_events_timeout
                
                open_or_closed = "open" if is_gate_open else "closed"

                say_it(f"Gate will be {open_or_closed} for {gate_open_timeout} seconds.")
                
                step = 30

                
                self.last_process_started = datetime.datetime.now()
                
                for i in range(1, gate_open_timeout, step): 
                    #say_it
                    print(f"{gate_open_timeout - i + 1} seconds remaining. {datetime.datetime.now()}")
                    time.sleep(step)

                
                #say_it
                print("Gate will close now.")
                print("Getting more events")
                gate_close()
                color_toggle("red", "off")
            else:
                #say_it("Not enough clear images.")
                print("Not enough clear images")
                self.event_threads.remove(src_path)
                self.last_process_started = datetime.datetime.now() - datetime.timedelta(seconds=ignore_events_timeout+1)
                print("Now event threads: ", self.event_threads)
                open(info_path, "w").write(json.dumps({"status" : "filtered_all"}))
        else:
            print("Race condition")
        
    # except:
    #     print("ERROR: Event processing failed", sys.exc_info()[0])
    # finally:
        #self.event_threads.remove(src_path)
        
        print(f"~~~~~ Releasing thread: {src_path}. Event Process Time: {int((datetime.datetime.now() - event_process_start_ts).total_seconds())} seconds. ~~~")
        #self.lock.release()
        color_toggle("red", "off")
        color_toggle("green", "off")
        



class EventHandler(FileSystemEventHandler):
    def __init__(self):
        self.event_threads = []
        self.lock = threading.Lock()
        self.last_process_started = None


    def on_created(self, event: FileSystemEvent) -> None:
        event_ts = datetime.datetime.now()


        
        if os.path.isdir(event.src_path):
            if "motion_" in event.src_path and event.src_path not in self.event_threads:                
                time_since_last_process = (event_ts - self.last_process_started).total_seconds() if self.last_process_started else 10000000

                info_path = event.src_path.replace("motions", "infos").replace("motion_", "info_")
                info_path = info_path +"/data_actions.json"

                data_actions = {"status" : "validating"}

                if time_since_last_process < ignore_events_timeout:
                    print(f"Ignoring event {event} after {time_since_last_process}s since last processing started.")
                    
                    data_actions["status"] = "post_action_timeout"
                    
                else:
                    print(f"Detected event: {event.src_path} ..............")
                    event_thread = threading.Thread(target = process_event, args = (self, event.src_path,))
                    
                    data_actions["status"] = "processing"
                    
                    event_thread.start()

                with open(info_path, "w") as info_file:
                    info_file.write(json.dumps(data_actions))

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
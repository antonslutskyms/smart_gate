from flask import Flask, jsonify, request

import os
import json
import sys

import run_smart_gate as rsg

import os
#import azure.cognitiveservices.speech as speechsdk

import threading
from jinja2 import Environment, FileSystemLoader

import actuators as act

STATIC = './motions'

app = Flask(__name__, static_folder=STATIC)

system_prompt = "How many pictures do you see?"

system_prompt_2="""You are a gate keeping robot.  
    Your job is to keep pets that go through the gate from bringing in rodents, birds or snakes.
 
    Analyze the set of images and determine if these pets should be allowed through the gate.  
    If any of the pets in the images should not be allowed through, none of the pets should be allowed.


    Respond Yes or No using the following JSON structures:
    Yes: {"is_allowed" : "Yes" }
    No: {"is_allowed" : "No" }
                """


env = Environment(loader = FileSystemLoader('templates'))
copilot_template = env.get_template('copilot.html')
home_template = env.get_template('home.html')
last_event_template = env.get_template('last_event.html')

# This example requires environment variables named "SPEECH_KEY" and "SPEECH_REGION"
#speech_config = speechsdk.SpeechConfig(subscription=os.environ.get('SPEECH_KEY'), region=os.environ.get('SPEECH_REGION'))
#audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

# The neural multilingual voice can speak different languages based on the input text.
#speech_config.speech_synthesis_voice_name='en-US-AvaMultilingualNeural'

#speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
#speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

def say_it(text = "Speech system test"):
    pass
    # speech_synthesis_result = speech_synthesizer.speak_text_async(text).get()
    
    # stream = speechsdk.AudioDataStream(speech_synthesis_result)

    # save_to = f"{STATIC}/latest.wav"
    # print("SaveTO: ", save_to)

    # stream.save_to_wav_file(save_to)
    
    # if speech_synthesis_result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    #     print("Speech synthesized for text [{}]".format(text))
    # elif speech_synthesis_result.reason == speechsdk.ResultReason.Canceled:
    #     cancellation_details = speech_synthesis_result.cancellation_details
    #     print("Speech synthesis canceled: {}".format(cancellation_details.reason))
    #     if cancellation_details.reason == speechsdk.CancellationReason.Error:
    #         if cancellation_details.error_details:
    #             print("Error details: {}".format(cancellation_details.error_details))
    #             print("Did you set the speech resource key and region values?")

@app.route('/call_copilot', methods=['POST', 'GET'])
def call_copilot():
    
    content = json.loads(request.data)
    print("Content: ", content)
    _system_prompt = content["prompt"]
    print("System Prompt: ", _system_prompt)

    events_root_dir = content["event_id"] #find_latest_event()[0]

    print(f"events_root_dir: {events_root_dir}")

    data_actions = []

    for filename in os.listdir(events_root_dir):
        file_path = os.path.join(events_root_dir, filename)
        if os.path.isfile(file_path):
            data_actions.append({"type": "image", "path": filename})

    print("Data Actions: ", data_actions)


    prompt, image_urls = rsg.render_prompt(data_actions, images_root_dir = events_root_dir)
    print("================== PROMPT ================")
    print(prompt, len(image_urls))
    print("==========================================")
    
    llm_response, llm_time = rsg.llm_task(user_prompt = prompt, 
                system_prompt=_system_prompt, 
                image_urls = image_urls)

    response = {"raw_response" : llm_response}
    try:
        response = json.loads(llm_response)
        
    except:
        print("Error processing LLM Response: ", llm_response)


    say_it(llm_response)
    

    print("============== RESULT ================")
    print(response)
    print(f"============== RESULT (in {llm_time}s) ================")



    return jsonify(response)

@app.route('/copilot')
def copilot():

    event_id = request.args.get('event_id')



    latest_event = event_id #find_latest_event()

    image_filter = None

    try:
        image_filter_req = request.args.get('image_filter')
        print(f"image_filter_req: {image_filter_req}")
        image_filter = json.loads(request.args.get('image_filter')) 
    except:
        print("Image filter not found")

    info_path = latest_event.replace("motions", "infos").replace("motion_", "info_")
    info_path = info_path + "/data_actions.json"

    data_info = None
    
    if os.path.isfile(info_path):
        data_info = json.loads(open(info_path).read())

    filtered_images = [d["path"] for d in data_info["filtered_data_actions"]] if data_info and "filtered_data_actions" in data_info else []

    image_filter_prompt = data_info["image_filter_prompt"] if data_info and "image_filter_prompt" in data_info else ""
    event_analysis_prompt = data_info["event_analysis_prompt"] if data_info and "event_analysis_prompt" in data_info else ""

    images = dump_images(latest_event, image_filter, filtered_images)

    copilot_html = copilot_template.render(latest_event = latest_event, 
                                            image_filter_prompt=image_filter_prompt,
                                            event_analysis_prompt=event_analysis_prompt,
                                            images = images,
                                            data_info = data_info)

    return copilot_html


def find_latest_event():
    dirs = []
    for d in os.listdir(STATIC):
        file_path = os.path.join(STATIC, d)

        if os.path.isdir(file_path):
            dirs.append(file_path)

    return sorted(dirs, key=lambda x: os.path.getctime(x), reverse=True)


def dump_images(directory, image_filter, 
                    filtered_images = None, 
                    img_height_px=80,
                    show_filename = True,
                    show_image = True,
                    show_info = True
                    ):
    images = "<table width='100%' border=1>"

    i = 1
    for filename in os.listdir(directory):
        
        if not image_filter or i in image_filter:

            file_path = os.path.join(directory, filename)

            info_path = file_path.replace("motions", "infos").replace("motion_", "info_").replace("event_", "info_").replace(".png", ".json")

            if os.path.isfile(file_path):
                images += "<tr>"

                info_data = ""
                if os.path.isfile(info_path):
                    info_data = open(info_path).read()

                highlight_color = "gray"
                if filtered_images and filename in filtered_images:
                    highlight_color = "red"

                if show_filename:
                    images += f"<td width='15%'>{filename}</td>"
    
                if show_image:
                    images += f"<td><img height='{img_height_px}px' src='{file_path}' style='border: {highlight_color} solid 5px'/></td>"
    
                if show_info:
                    images += f"<td>{info_data}</td></div>"
                    
                images += "</tr>"
        i += 1

    images += "</table>"
    return images


@app.route('/gate_ctrl')
def gate_ctrl():
    #try:
    with open("gate_ctrl.json", "w") as out:
        is_enabled = request.args.get('enabled')
        print("is_enabled: ", is_enabled)

        is_enabled = True if is_enabled == "True" else False
        print("is_enabled: ", is_enabled)

        out.write(json.dumps({"is_enabled" : is_enabled}))
    #
    
    return "OK"

@app.route('/simulate')
def simulate():

    print("Simulate event called.")
    event_id = request.args.get('id').split("/")[-1]
    print(f"Simulating event: {event_id}")
    os.system(f"./simulate.sh {event_id}")

    return "OOOOOOK"

@app.route('/gate')
def gate():

    state = request.args.get('state')

    try:
        if "open" == state:            
            print("ATTENTION: GATE OPENING")
            os.system(f"./open.sh")
            
        elif "close" == state:
            print("ATTENTION: GATE CLOSING")
            os.system(f"./close.sh")
    except:
            print("WARNING: Unable to close gate")
    
    return state

@app.route('/last_event')
def last_event():

    directory = find_latest_event()[0]
    
    print("Latest event dir:", directory)
    
    images = dump_images(directory, None)

    dir_list = "<br/>".join(os.listdir(directory))

    latest_info = ""
    try:
        latest_info = open("motions/latest_info.json").read()
    except:
        print("WARNING: Unable to load latest info")

    return last_event_template.render(directory = directory, 
                                        images = images, 
                                        latest_info = latest_info)


@app.route('/')
def home():

    directories = find_latest_event()

    last_event = directories[0] if "event_id" not in request.args else request.args.get("event_id")

    images = dump_images(last_event, None, show_filename=False, show_info=False)

    i = 0
    recent_events = "<table width='100%' border=1>"

    recent_events += "<tr>"
    recent_events += f"<th>Status</th>"
    recent_events += f"<th width='17%'>Event ID</th>"
    recent_events += f"<th>Event Data</th>"
    recent_events += f"<th>Target</th>"
    recent_events += f"<th>TTA</th>"
    recent_events += f"<th>FT</th>"
    recent_events += f"<th>RT</th>"
    recent_events += f"<th>DC</th>"
    recent_events += "</tr>\n"


    for dir in directories[:100]:
        recent_events += "<tr>"
        info_path = dir.replace("motions", "infos").replace("motion_", "info_")
        info_path = info_path +"/data_actions.json"
        
        indicator = "Ignored"
        indicator_color = "gray"

        print("Info_file: ", info_path)

        time_to_action = -1
        llm_filtering_time = -1
        llm_response_time = -1
        event_data_collection_time = -1
        
        filtered_data_actions = []
        unfiltered_data_actions = []

        has_data_actions = os.path.isfile(info_path)
        if has_data_actions:
            info_js = open(info_path).read()
            print("JSON: ", info_js)

            try:
                info_file = json.loads(info_js)
                print("Info file: ", info_file)

                if "status" in info_file:
                    indicator = info_file["status"]
                    indicator_color = "black"


                if "is_gate_open" in info_file:
                    is_gate_open = info_file["is_gate_open"] 
                    indicator = "Allowed" if is_gate_open else "Denied"
                    indicator_color = "green" if is_gate_open else "false"  

                time_to_action = info_file.get("time_to_action", -1)
                llm_filtering_time = info_file.get("llm_filtering_time", -1)
                llm_response_time = info_file.get("llm_response_time", -1)
                event_data_collection_time = info_file.get("event_data_collection_time", -1)
                unfiltered_data_actions = info_file.get("unfiltered_data_actions", [])
                filtered_data_actions = info_file.get("filtered_data_actions", [])
            except:
                print("Info structure unsupported: ", info_path, info_js)
        
        indicator = f"<font style='color: {indicator_color}; font-weight: bold'>{indicator}</font>"

        recent_events += f"<td>{indicator}</td>"
        recent_events += f"<td><a href='copilot?event_id={dir}'>{dir}</a></td>"

        img_height = 70 if has_data_actions else 20

        recent_events += "<td width='40%'>"
        for image_path in os.listdir(dir):
    
            img_src = os.path.join(dir, image_path)
            print("Img Src: ", img_src)
            recent_events += f"\n<img style='border:3px black solid' src='{img_src}' height='{img_height}px'/>\n"

        recent_events += "</td>"


        recent_events += "<td width='40%'>"
        for image_path in unfiltered_data_actions:
            border_color = "red" if image_path in filtered_data_actions else "gray"
            img_src = os.path.join(dir, image_path["path"])
            print("Img Src: ", img_src)
            recent_events += f"<img style='border:3px {border_color} solid' src='{img_src}' height='70px'/>\n"

        recent_events += "</td>"
        recent_events += f"<td align='center' valign='center'>{round(time_to_action)}</td>"
        recent_events += f"<td align='center' valign='center'>{round(llm_filtering_time)}</td>"
        recent_events += f"<td align='center' valign='center'>{round(llm_response_time)}</td>"
        recent_events += f"<td align='center' valign='center'>{round(event_data_collection_time)}</td>"

        recent_events += "</tr>\n"

    recent_events += "</table>"

    is_enabled = True

    if os.path.isfile("gate_ctrl.json"):
        is_enabled = json.loads(open("gate_ctrl.json").read())["is_enabled"]
        print(f"gate_ctrl.json: is_enabled |{is_enabled}|")
        #is_enabled = True if is_enabled else False

    enable_disable = "Disable" if is_enabled else "Enable"

    print("is_enabled status", is_enabled, enable_disable)

    return home_template.render(recent_events = recent_events, last_event=last_event, 
                                event_images = images, is_enabled=(not is_enabled), enable_disable=enable_disable )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
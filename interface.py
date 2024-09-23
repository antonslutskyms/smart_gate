from flask import Flask, jsonify, request

import os
import json
import sys

import run_smart_gate as rsg

import os
#import azure.cognitiveservices.speech as speechsdk

import threading
from jinja2 import Environment, FileSystemLoader

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
    
    llm_response = rsg.llm_task(user_prompt = prompt, 
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
    print("============== RESULT ================")



    return jsonify(response)

@app.route('/copilot')
def copilot():

    event_id = request.args.get('event_id')



    latest_event = event_id #find_latest_event()

    image_filter = None

    try:
        image_filter_req = request.args.get('image_filter')
        print(f"image_filter_req: {image_filter_req}")
        image_filter = json.load(request.args.get('image_filter')) 
    except:
        print("Image filter not found")

    images = dump_images(latest_event, image_filter)

    copilot_html = copilot_template.render(latest_event = latest_event, 
                                            system_prompt=system_prompt,
                                            images = images)

    return copilot_html


def find_latest_event():
    dirs = []
    for d in os.listdir(STATIC):
        file_path = os.path.join(STATIC, d)

        if os.path.isdir(file_path):
            dirs.append(file_path)

    return sorted(dirs, key=lambda x: os.path.getctime(x), reverse=True)


def dump_images(directory, image_filter):
    images = "<table width='100%' border=1>"

    i = 1
    for filename in os.listdir(directory):
        
        if not image_filter or i in image_filter:

            file_path = os.path.join(directory, filename)

            info_path = file_path.replace("motions", "infos").replace("motion_", "info_").replace("event_", "info_").replace(".png", ".json")

            if os.path.isfile(file_path):
                images += "<tr>"
                info_data = open(info_path).read()

                images += f"<td width='15%'>{filename}</td><td><img height='100px' src='{file_path}' style='border: green solid 3px'/></td><td>{info_data}</td></div>"
                images += "</tr>"
        i += 1

    images += "</table>"
    return images

@app.route('/last_event')
def last_event():

    directory = find_latest_event()[0]
    
    print("Latest event dir:", directory)
    
    images = dump_images(directory)

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

    last_event = directories[0]

    i = 0
    recent_events = ""
    for dir in directories:
        recent_events += f"<br/><a href='copilot?event_id={dir}'>{dir}</a>"

    


    return home_template.render(recent_events = recent_events, last_event=last_event)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
from flask import Flask, jsonify, request

import os
import json
import sys

import run_smart_gate as rsg

import os
import azure.cognitiveservices.speech as speechsdk

import threading

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


# This example requires environment variables named "SPEECH_KEY" and "SPEECH_REGION"
speech_config = speechsdk.SpeechConfig(subscription=os.environ.get('SPEECH_KEY'), region=os.environ.get('SPEECH_REGION'))
audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

# The neural multilingual voice can speak different languages based on the input text.
speech_config.speech_synthesis_voice_name='en-US-AvaMultilingualNeural'

#speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

def say_it(text = "Speech system test"):

    speech_synthesis_result = speech_synthesizer.speak_text_async(text).get()
    
    stream = speechsdk.AudioDataStream(speech_synthesis_result)

    save_to = f"{STATIC}/latest.wav"
    print("SaveTO: ", save_to)

    stream.save_to_wav_file(save_to)
    
    if speech_synthesis_result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("Speech synthesized for text [{}]".format(text))
    elif speech_synthesis_result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = speech_synthesis_result.cancellation_details
        print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            if cancellation_details.error_details:
                print("Error details: {}".format(cancellation_details.error_details))
                print("Did you set the speech resource key and region values?")

@app.route('/call_copilot', methods=['POST'])
def call_copilot():
    
    content = json.loads(request.data)
    print("Content: ", content)
    _system_prompt = content["prompt"]
    print("System Prompt: ", _system_prompt)

    #response = {"response": "yes"}


    events_root_dir = find_latest_event()

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
    latest_event = find_latest_event()

    images = dump_images(latest_event)

    call_copilot_func = """



        function call_copilot(){
                    
            const apiUrl = '/call_copilot';

            document.getElementById("system_prompt").disabled = true;
            document.getElementById("call_copilot").disabled = true;
            fetch(apiUrl,{
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json"
                            },
                            body: JSON.stringify({
                                prompt: document.getElementById("system_prompt").value
                            })
                        })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                console.log(data);
                document.getElementById("llm_response").innerHTML = JSON.stringify(data)

                var combined_prompt = document.getElementById("system_prompt").value.trim();
                combined_prompt = combined_prompt + '\\n\\n'+JSON.stringify(data)+'\\n\\n';
                console.log(combined_prompt);

                document.getElementById("system_prompt")
                document.getElementById("system_prompt").value = combined_prompt;

                document.getElementById("say_it").src = 'motions/latest.wav?t=' + new Date().getTime();
                document.getElementById("say_it").play();
                document.getElementById("call_copilot").disabled = false;
                document.getElementById("system_prompt").disabled = false;

            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById("llm_response").innerHTML = '<b>Error: '+error+'</b>'
            });
        }
    """

    return f"""
    <html>
        <body>
            <center><h1>{latest_event}</h1></center>
            <table border=1 width='100%'>
                <tr>
                    <td width='50%'>
                        <h2>System Prompt:</h2>
                        <textarea cols='100' rows='15' id='system_prompt'>{system_prompt}</textarea>
                        <h2>Data:</h2>
                        <div>
                        {images}
                        </div>
                    </td>
                    <td>
                        <div id='llm_response'>&nbsp;</div>
                    </td>
                </tr>
            </table>
            <center>
                <input type='button' id='call_copilot' value='Submit' style='height:50px;width:200px' onclick='call_copilot()'/>
            </center>
            <script language='javascript'>
                {call_copilot_func}
            </script>
            <audio id="say_it" src="motions/latest.wav"></audio>
        </body>
    </html>
    """


def find_latest_event():
    dirs = []
    for d in os.listdir(STATIC):
        file_path = os.path.join(STATIC, d)

        if os.path.isdir(file_path):
            dirs.append(file_path)

    return sorted(dirs, key=lambda x: os.path.getctime(x), reverse=True)[0]


def dump_images(directory):
    images = ""

    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            images += f"<img height='100px' src='{file_path}'/>"
    
    return images

@app.route('/last_event')
def last_event():

    directory = find_latest_event()
    
    print("Latest event dir:", directory)
    
    
    images = dump_images(directory)

    return f"""
    <html>
        <body>
            <center><h1>{directory}</h1></center>
            
            <table border=1 width='100%' >
                <tr>
                    <td align='center' valign='center' width='75%'>
                        {images}
                    </td>
                    <td>
                        {"<br/>".join(os.listdir(directory))}
                    </td>
                </tr>
            </table>    
        </body>
    </html>
    """

@app.route('/')
def home():


    


    return """
        <html>
            <body>
                <table width='100%' height='100%' border=1 align='center' valign='center' >
                    <tr>
                        <th>
                            <h1>
                                Current View
                            </h1>
                        </th>
                        <th>
                            <h1>Last Motion</h1>
                        </th>
                    </tr>
                    <tr>
                        <td align='center' valign='center' >
                            <img src='motions/current_frame.png' id='current_frame'/>
                        </td>
                        <td align='center' valign='center' >    
                           <img src='motions/event_current.png' id='event_current'/>
                        </td>
                    </tr>
                    <tr>
                        <td colspan=2 width='100%'>
                            <iframe src="/last_event" width='100%' height='3000px' id='last_events'></iframe>
                        </td>
                    </tr>
                </table>
                
                <script language='javascript'>
                    setInterval(function () {document.getElementById("current_frame").src = 'motions/current_frame.png?t=' + new Date().getTime();}, 300);
                    setInterval(function () {document.getElementById("event_current").src = 'motions/event_current.png?t=' + new Date().getTime();}, 300);
                    setInterval(function () {document.getElementById("last_events").contentWindow.location.reload()}, 3000);
                </script>
            </body>
        </html>
    """

if __name__ == '__main__':
    app.run(debug=True)
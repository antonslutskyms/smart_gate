import os
from openai import AzureOpenAI

from PIL import Image 
import requests 
import os
import base64
from io import BytesIO
from pathlib import Path
import json

import copy 
import json
import sys

import datetime

from jinja2 import Environment, FileSystemLoader

from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential

from azure.ai.inference.models import SystemMessage, UserMessage


from azure.ai.inference.models import TextContentItem, ImageContentItem, ImageUrl

phi35_client = ChatCompletionsClient(
    endpoint=os.environ["PHI35_VISION_ENDPOINT"],
    credential=AzureKeyCredential(os.environ["PHI35_VISION_KEY"]),
)




def load_image(image_file):
    print(f"----------- Loading image: {image_file} ----------------")
    img_base64_pref = 'data:image/'

    if image_file.startswith('http://') or image_file.startswith('https://'):
        response = requests.get(image_file)
        image = Image.open(BytesIO(response.content)).convert('RGB')
    elif image_file.startswith(img_base64_pref):
        print(f"-- Found image: {image_file}")
        mime_parts = image_file.split(";")
        print(f"------ mime_parts: {mime_parts}")
        mime_str = mime_parts[0]
        print(f"------ mime_str: {mime_str}")
        image_ext = mime_str.split("/")[1]
        print(f"------ image_ext: {image_ext}")

        prefix_sz = len(mime_str)+len("base64,")
        print(f"------ prefix_sz: {prefix_sz}")


        print("------ base64 image detected")
        img_data = image_file[prefix_sz:]
        print(f"------ Loaded image data: {img_data[:300]}")
        
        msg = base64.b64decode(img_data)
        buf = BytesIO(msg)
        print("------ Buffer created")
        return Image.open(buf).convert('RGB'), image_ext
    else:
        image = Image.open(image_file).convert('RGB'), image_file.split(".")[-1]
    
    return image

    
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_ENDPOINT_KEY"),  
    api_version= os.getenv("AZURE_OPENAI_API_VERSION"), #"2024-02-01",
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    )

print("Initialized AzureOpenAI client")

deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

print(f"Using Deployment: {deployment_name}")


env = Environment(loader = FileSystemLoader('templates'))
template = env.get_template('smart_gate_template.jinja')

print("Templates loaded")



EXT_TO_MIMETYPE = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.svg': 'image/svg+xml'
}

def local_image_loader(local_image_name, images_root_dir):
    print(f"Loading image {local_image_name} from {images_root_dir}")
    return load_image(f"{images_root_dir}/{local_image_name}")


def image_to_data_url(image: Image.Image, ext: str) -> str:
    ext = ext.lower()
    if ext not in EXT_TO_MIMETYPE:
        ext = '.jpg'  # Default to .jpg if extension is not recognized
    mimetype = EXT_TO_MIMETYPE[ext]
    buffered = BytesIO()
    image_format = 'JPEG' if ext in ['.jpg', '.jpeg'] else ext.replace('.', '').upper()
    image.save(buffered, format=image_format)
    encoded_string = base64.b64encode(buffered.getvalue()).decode('utf-8')
    data_url = f"data:{mimetype};base64,{encoded_string}"
    return data_url

def render_prompt(data_actions, images_root_dir = "cat_pics"):

    data_actions = copy.deepcopy(data_actions)

    images_urls = []
    img_cnt = 0

    for data_action in data_actions:
        if data_action["type"] == "image":
            img_cnt += 1
            image_path = data_action["path"] 
            
            image, image_ext = local_image_loader(image_path, images_root_dir = images_root_dir)

            base64_image = image_to_data_url(image, image_ext)
            images_urls.append(base64_image)
            print("image base64:", base64_image[:100])    
            data_action["path"] = f"<|image_{img_cnt}|>"

    prompt = template.render(data = data_actions)
    return prompt, images_urls

def llm_task_phi3(user_prompt, image_urls, system_prompt):  

    

    content = [
        
    ]
    content.append(TextContentItem(text=system_prompt))

    for image_url in image_urls:
        content.append(ImageContentItem(image_url = ImageUrl(url=image_url)))

    

    print("System Prompt:", system_prompt)
    print("User Content: ", len(content))


    llm_start_ts = datetime.datetime.now()
    
    response = phi35_client.complete(
                        messages=[
                            #SystemMessage(content = content),
                            #SystemMessage(content = [TextContentItem(text="You are a useful AI bot that analyzes images.")]),
                            UserMessage(content=content),
                        ],
                        temperature=0,
                        top_p=1,
                        max_tokens=2048,
                )
    
    llm_time = int((datetime.datetime.now() - llm_start_ts).total_seconds())
    
    return response.choices[0].message.content, llm_time


def llm_task(user_prompt, image_urls, system_prompt):    
    
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print("~~~~~~~~~~~~~~~~ START LLM TASK ~~~~~~~~~~~~~~~~~~~")
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

    print("\nSYSTEM PROMPT (INSTRUCTIONS):\n----------------------------------------------------------------------------------------")
    print(system_prompt)
    print("\n\nUSER PROMPT (IMAGES):\n----------------------------------------------------------------------------------------")
    print(user_prompt)
    print("\n----------------------------------------------------------------------------------------")

    llm_start_ts = datetime.datetime.now()

    

    user_content = [{
                "type": "text",
                "text": user_prompt,
                }]
    
    for image_url in image_urls:
        user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                }
            })

    messages=[]

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role" : "user", "content" : user_content})  
  
    response = client.chat.completions.create(
        model=deployment_name, # model = "deployment_name".
        messages=messages
    )

    fixed_json = response.choices[0].message.content

    fixed_json = fixed_json.replace("```json", "").replace("```", "")
    print(f"~~~~~~~~~~~~~~~~~ {deployment_name} Response Json ~~~~~~~~~~~~~~~~~")
    print(fixed_json)

    llm_time = int((datetime.datetime.now() - llm_start_ts).total_seconds())

    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print(f"~~~~~~~~~~ END LLM TASK [{llm_time}s] ~~~~~~~~~~~~~~~")
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    return fixed_json, llm_time


if __name__ == "__main__":

    events_root_dir = sys.argv[1]
    print(f"events_root_dir: {events_root_dir}")

    data_actions = []

    for filename in os.listdir(events_root_dir):
        file_path = os.path.join(events_root_dir, filename)
        if os.path.isfile(file_path):
            data_actions.append({"type": "image", "path": filename})

    print("Data Actions: ", data_actions)


    prompt, image_urls = render_prompt(data_actions, images_root_dir = events_root_dir)
    print("================== PROMPT ================")
    print(prompt, len(image_urls))
    print("==========================================")
    
    llm_response = llm_task(user_prompt = prompt, 
                system_prompt="""You are a gate keeping robot.  
    Your job is to keep pets that go through the gate from bringing in rodents, birds or snakes.
 
    Analyze the set of images and determine if these pets should be allowed through the gate.  
    If any of the pets in the images should not be allowed through, none of the pets should be allowed.


    Respond Yes or No using the following JSON structures:
    Yes: {"is_allowed" : "Yes" }
    No: {"is_allowed" : "No" }
                """, 
                image_urls = image_urls)


    print("============== RESULT ================")
    print(json.loads(llm_response))
    print("============== RESULT ================")
import speech_recognition
import openai
import sys
import whisper
import time
import pyttsx3
import ffmpeg
import requests
import re

from io import BytesIO
import asyncio
import json
import time
import aiohttp
import subprocess
import vlc

#Uberduck stuff
API_KEY = "pub_uberduckapikey"
API_SECRET = "pk_uberduckapisecret"
API_ROOT = "https://api.uberduck.ai"

#OpenAI API Key
openai.api_key = 'sk-openaiapikey'

glados = vlc.MediaPlayer("https://uberduck-audio-outputs.s3-us-west-2.amazonaws.com/d1622615-8729-4463-a65a-681c65868fe9/audio.wav")
stop = None

def speak(text):
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    engine.setProperty('voice', "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_ZIRA_11.0")
    engine.say(text)
    engine.runAndWait()

async def query_uberduck(text, voice="glados-p2"):
    max_time = 15 #define timeout
    async with aiohttp.ClientSession() as session:
        #assable the uberduck POST request
        url = f"{API_ROOT}/speak"
        data = json.dumps(
            {
                "speech": text,
                "voice": voice,
            }
        )
        start = time.time()
        print("| requesting uberduck voice")
        #sending the uberduck POST request
        async with session.post(
            url,
            data=data,
            auth=aiohttp.BasicAuth(API_KEY, API_SECRET),
        ) as r:
            if r.status != 200:
                raise Exception("Error synthesizing speech", await r.json())
            #wait for the session uuid
            uuid = (await r.json())["uuid"]
            print(f"| {API_ROOT}/speak-status?uuid={uuid}")
        while True:
            if time.time() - start > max_time:
                raise Exception("Request timed out!")
            await asyncio.sleep(1)
            status_url = f"{API_ROOT}/speak-status"
            #GET the status of the request
            async with session.get(status_url, params={"uuid": uuid}) as r:
                #print(r)
                if r.status != 200:
                    continue
                #wait for response
                response = await r.json()
                #print(response)
                #grep the web url for the finished .wav audio file
                if response["path"]:
                    async with session.get(response["path"]) as r:
                        print(response["path"])
                        #return the web url for the .wav audio file
                        return response["path"]
                        #return BytesIO(await r.read())

def callback(recognizer, audio):
    # received audio data, now we'll recognize it using Google Speech Recognition
    print("| checking audio")
    text = None
    try:
        #recognize speech with google web api
        text = recognizer.recognize_google(audio, language="en-US", show_all=False)
        #text = recognizer.recognize_whisper(audio, language="english")
    except speech_recognition.UnknownValueError:
        print("| Google Speech Recognition could not understand audio")
    except speech_recognition.RequestError as e:
        print("| Could not request results from Google Speech Recognition service; {0}".format(e))
        
    if text != None:
        #text = text.lower()
        print(f"\n\n{text}")
        #response = openai.ChatCompletion.create(
        #    model="gpt-3.5-turbo",
        #    messages=[
        #        {"role": "system", "content": "You act like GLaDOS and you answer all my requests in a spitefull and sarcastic tone, knowing that humans are way less intelligent than machines."},
        #        {"role": "user", "content": f"{text}"}
        #    ]
        #    #max_tokens=100,
        #    #temperature=0.7
        #    #top_p=1,
        #    #n=1,
        #    #stream=False,
        #    #logprobs=None,
        #)
        response = openai.Completion.create(
            model="text-davinci-002",
            prompt=f"You act like GLaDOS and you answer all my requests in her mean and sarcastic manner!\nDespite being stubborn you still do everthing i want.\n{text}",
            max_tokens=100,
            temperature=0.7
            #top_p=1,
            #n=1,
            #stream=False,
            #logprobs=None,
        )

        answer = response.choices[0]['text'] #answer structur for openai.Completion.create
        #answer = response.choices[0]['message']['content'] #answer structur for openai.ChatCompletion.create
        
        #call the handler function to do the output stuff, so we can finish the work of the callback function
        asyncio.run(response_processing(text, answer))

async def listening_handler():
    global listener_started
    global stop
    listener_started = False
    while True:
        if listener_started and glados.is_playing():
            #stop listener while glados is speaking
            stop(wait_for_stop=False)
            listener_started = False
            print("| listener stopped")
        else:
            if not listener_started and not glados.is_playing():
                #start lister if not running yet and glados finished speaking
                recognizer = speech_recognition.Recognizer()
                microphone = speech_recognition.Microphone()
                with microphone as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.2)
                    print("| noise calibrated")
                stop = recognizer.listen_in_background(microphone, callback, phrase_time_limit=10)
                listener_started = True
                print("| listener started")
        await asyncio.sleep(0.5)

async def response_processing(text, answer):
    #print(f"\n\n{answer}")
    #speak(answer)
    
    #request voice from uberduck, return url to .wav
    url = await query_uberduck(answer)
    
    #play .wav with vlc
    global glados
    glados = vlc.MediaPlayer(url)
    print(f"\n\n{answer}")
    print("| playing audio")
    glados.play()
    
    #do tasks according to my input
    await task_handler(text)
    
async def task_handler(text):
    if re.search('turn * on', text):
        code = requests.get("http://192.168.0.179/win&T=1")
        print("| light request send, turning on")
    if re.search('turn * off', text):
        code = requests.get("http://192.168.0.179/win&T=0")
        print("| light request send, turning off")
    
async def init():
    #start vlc instance and define less logging output, idk if this works at all, lol
    vlcInstance = vlc.Instance("--no-xlib")

    #start listening handler
    await listening_handler()
    
    #the keep-alive-loop, parallel tasks can be defined in the loop if neccessary
    while True:
        try:
            time.sleep(2)
            #print(".")
        except KeyboardInterrupt:
            sys.exit()
        
#main entry point
if __name__ == "__main__":
    asyncio.run(init())
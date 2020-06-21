#!/usr/bin/python3

import traceback
import alsaaudio
import paho.mqtt.client as mqtt
import subprocess
import time
import os

# Edit these
MQTT_HOST = 'localhost'
MQTT_PORT = 1883
MQTT_USERNAME = ''
MQTT_PASSWORD = ''


# Do not edit below
MIXER_NAME = alsaaudio.mixers()[0]

def announceVolume():
    volume = subprocess.Popen("amixer get " + MIXER_NAME + " | grep % | awk '{print $4}'| sed 's/[^0-9\]//g'", shell=True, stdout=subprocess.PIPE).stdout.read()
    volume = str(volume, encoding = 'utf-8').replace("\n", '')
    client.publish(mqttTopicPrefix + 'volume', volume, retain=True)
    # client.publish(mqttTopicPrefix + 'volume', str(mixer.getvolume()[0]), retain=True)

def announceBluetooth():
    state = subprocess.Popen('hciconfig hci0 | grep -oP "(UP|DOWN)"', shell=True, stdout=subprocess.PIPE).stdout.read()
    state = str(state, encoding = 'utf-8')
    client.publish(mqttTopicPrefix + 'bluetooth', '1' if 'UP' in state else '0', retain=True)



def onMessage(client, userdata, message):
    service = message.topic.replace(mqttTopicPrefix, '')

    if (service == 'volume/set'):
        volume = int(message.payload)
        if (volume >= 0 and volume <= 100):
            os.system('amixer set ' + MIXER_NAME + ' ' + str(volume) + '% -q');
            # mixer.setvolume(volume)
        announceVolume()


    if (service == 'bluetooth/set'):
        payload = str(message.payload, encoding = 'utf-8')
        if (payload == '0'):
            os.system('hciconfig hci0 down')
        elif (payload == '1'):
            os.system('hciconfig hci0 up')
        elif (payload == '2'):
            os.system('hciconfig hci0 down')
            os.system('hciconfig hci0 up')
        announceBluetooth()



client = None
mixer = None

try:
    mac = subprocess.Popen('hciconfig hci0 | grep -oP "([A-F0-9]{2}\:?){6}"', shell=True, stdout=subprocess.PIPE).stdout.read()
    mac = str(mac, encoding = 'utf-8').replace("\n", "")
    mqttTopicPrefix = 'btspeaker/' + mac.replace(':', '') + '/'

    mixer = alsaaudio.Mixer('Headphone')

    client = mqtt.Client()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.connect(MQTT_HOST, MQTT_PORT)
    client.subscribe([(mqttTopicPrefix + 'volume/set', 0), (mqttTopicPrefix + 'bluetooth/set', 0)])
    client.on_message = onMessage
    client.loop_start()

    while True:
        announceVolume()
        announceBluetooth()
        time.sleep(60)


except KeyboardInterrupt as ex:
    print("Manager cancelled by user")

except Exception as ex:
    print("How embarrassing. The following error occurred: {}".format(ex))
    traceback.print_exc()

finally:
    if client:
        client.loop_stop()
        client.disconnect()

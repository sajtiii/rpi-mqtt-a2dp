#!/usr/bin/python

import logging
import traceback
import alsaaudio
import paho.mqtt.client as mqtt
import subprocess
import time
import os


def announceVolume():
    client.publish(mqttTopicPrefix + 'volume', str(mixer.getvolume()[0]), retain=True)

def announceBluetooth():
    state = subprocess.Popen('hciconfig hci0 | grep -oP "(UP|DOWN)"', shell=True, stdout=subprocess.PIPE).stdout.read()
    client.publish(mqttTopicPrefix + 'bluetooth', '1' if 'UP' in state else '0', retain=True)



def onMessage(client, userdata, message):
    service = message.topic.replace(mqttTopicPrefix, '')

    if (service == 'volume/set'):
        volume = int(message.payload)
        if (volume >= 0 and volume <= 100):
            mixer.setvolume(volume)
        announceVolume()


    if (service == 'bluetooth/set'):
        print('set')
        if (message.payload == '0'):
            os.system('hciconfig hci0 down')
        elif (message.payload == '1'):
            os.system('hciconfig hci0 up')
        elif (message.payload == '2'):
            os.system('hciconfig hci0 down')
            os.system('hciconfig hci0 up')
        announceBluetooth()



client = None
mixer = None

try:
    mac = subprocess.Popen('hciconfig hci0 | grep -oP "([A-F0-9]{2}\:?){6}"', shell=True, stdout=subprocess.PIPE).stdout.read()
    mqttTopicPrefix = ('btspeaker/' + mac.replace(':', '') + '/').replace("\n", '')

    mixer = alsaaudio.Mixer('Headphone')

    client = mqtt.Client()
    client.connect('localhost')
    client.subscribe([(mqttTopicPrefix + 'volume/set', 0), (mqttTopicPrefix + 'bluetooth/set', 0)])
    client.on_message = onMessage
    client.loop_start()

    while True:
        announceVolume()
        announceBluetooth()
        time.sleep(5)


except KeyboardInterrupt as ex:
    logging.info("Manager cancelled by user")

except Exception as ex:
    logging.error("How embarrassing. The following error occurred {}".format(ex))
    traceback.print_exc()

finally:
    if client:
        client.loop_stop()
        client.disconnect()

#!/usr/bin/python3

"""Copyright (c) 2015, Douglas Otwell
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import time
import signal
import dbus
import dbus.service
import dbus.mainloop.glib
#import gobject
from gi.repository import GLib
import traceback
import paho.mqtt.client as mqtt
import subprocess

# Edit these
MQTT_HOST = 'localhost'
MQTT_PORT = 1883
MQTT_USERNAME = ''
MQTT_PASSWORD = ''

# Do not edit below
SERVICE_NAME = "org.bluez"
AGENT_IFACE = SERVICE_NAME + '.Agent1'
ADAPTER_IFACE = SERVICE_NAME + ".Adapter1"
DEVICE_IFACE = SERVICE_NAME + ".Device1"
PLAYER_IFACE = SERVICE_NAME + '.MediaPlayer1'
TRANSPORT_IFACE = SERVICE_NAME + '.MediaTransport1'

"""Utility functions from bluezutils.py"""
def getManagedObjects():
    bus = dbus.SystemBus()
    manager = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
    return manager.GetManagedObjects()

def findAdapter():
    objects = getManagedObjects();
    bus = dbus.SystemBus()
    for path, ifaces in objects.items():
        adapter = ifaces.get(ADAPTER_IFACE)
        if adapter is None:
            continue
        obj = bus.get_object(SERVICE_NAME, path)
        return dbus.Interface(obj, ADAPTER_IFACE)
    raise Exception("Bluetooth adapter not found")

class BluePlayer(dbus.service.Object):
    AGENT_PATH = "/blueplayer/agent"
#    CAPABILITY = "DisplayOnly"
    CAPABILITY = "NoInputNoOutput"

    bus = None
    adapter = None
    device = None
    deviceAlias = None
    player = None
    transport = None
    connected = None
    state = None
    status = None
    discoverable = None
    track = None
    mainloop = None
    mqttTopicPrefix = None

    def __init__(self):
        mac = subprocess.Popen('hciconfig hci0 | grep -oP "([A-F0-9]{2}\:?){6}"', shell=True, stdout=subprocess.PIPE).stdout.read()
        mac = str(mac, encoding = 'utf-8').replace("\n", "")
        self.mqttTopicPrefix = 'btspeaker/' + mac.replace(':', '') + '/'


    def start(self):
        """Subscribe to MQTT events"""
        client.subscribe([(self.mqttTopicPrefix + 'track/action', 0)])
        client.on_message = self.onMessage
        client.loop_start()

        """Initialize gobject and find any current media players"""
        #GObject.threads_init() 
        #gobject.threads_init()
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

        self.bus = dbus.SystemBus()
        dbus.service.Object.__init__(self, dbus.SystemBus(), BluePlayer.AGENT_PATH)

        self.bus.add_signal_receiver(self.playerHandler,
                bus_name="org.bluez",
                dbus_interface="org.freedesktop.DBus.Properties",
                signal_name="PropertiesChanged",
                path_keyword="path")

        self.registerAgent()

        adapter_path = findAdapter().object_path
        self.bus.add_signal_receiver(self.adapterHandler,
                bus_name = "org.bluez",
                path = adapter_path,
                dbus_interface = "org.freedesktop.DBus.Properties",
                signal_name = "PropertiesChanged",
                path_keyword = "path")


        self.findPlayer()

        """Start the BluePlayer by running the gobject mainloop()"""
        self.mainloop = GLib.MainLoop()
        self.mainloop.run()

    def findPlayer(self):
        """Find any current media players and associated device"""
        manager = dbus.Interface(self.bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        objects = manager.GetManagedObjects()

        player_path = None
        transport_path = None
        for path, interfaces in objects.items():
            if PLAYER_IFACE in interfaces:
                player_path = path
            if TRANSPORT_IFACE in interfaces:
                transport_path = path

        if player_path:
            self.connected = True
            self.getPlayer(player_path)
            player_properties = self.player.GetAll(PLAYER_IFACE, dbus_interface="org.freedesktop.DBus.Properties")
            if "Status" in player_properties:
                self.status = player_properties["Status"]
                self.announceStatus()
            if "Track" in player_properties:
                self.track = player_properties["Track"]
                self.announceTrack()

        if transport_path:
            self.transport = self.bus.get_object("org.bluez", transport_path)
            transport_properties = self.transport.GetAll(TRANSPORT_IFACE, dbus_interface="org.freedesktop.DBus.Properties")
            if "State" in transport_properties:
                self.state = transport_properties["State"]

    def getPlayer(self, path):
        """Get a media player from a dbus path, and the associated device"""
        self.player = self.bus.get_object("org.bluez", path)
        device_path = self.player.Get("org.bluez.MediaPlayer1", "Device", dbus_interface="org.freedesktop.DBus.Properties")
        self.getDevice(device_path)

    def getDevice(self, path):
        """Get a device from a dbus path"""
        self.device = self.bus.get_object("org.bluez", path)
        self.deviceAlias = self.device.Get(DEVICE_IFACE, "Alias", dbus_interface="org.freedesktop.DBus.Properties")
        self.announceDevice()

    def playerHandler(self, interface, changed, invalidated, path):
        """Handle relevant property change signals"""
        iface = interface[interface.rfind(".") + 1:]

        if iface == "Device1":
            if "Connected" in changed:
                self.connected = changed["Connected"]
                self.announceConnected()
        if iface == "MediaControl1":
            if "Connected" in changed:
                self.connected = changed["Connected"]
                self.announceConnected()
                if changed["Connected"]:
                    self.findPlayer()
        elif iface == "MediaTransport1":
            if "State" in changed:
                self.state = (changed["State"])
                self.announceState()
            if "Connected" in changed:
                self.connected = changed["Connected"]
                self.announceConnected()
        elif iface == "MediaPlayer1":
            if "Track" in changed:
                self.track = changed["Track"]
                self.announceTrack()
            if "Status" in changed:
                self.status = (changed["Status"])
                self.announceStatus()

    def adapterHandler(self, interface, changed, invalidated, path):
        """Handle relevant property change signals"""
        if "Discoverable" in changed:
                self.discoverable = changed["Discoverable"]
                self.announceDiscoverable()

    def announceTrack(self):
        client.publish(self.mqttTopicPrefix + 'track', '{"album":"' + (self.track['Album'] if 'Album' in self.track else '') + '","artist":"' + (self.track['Artist'] if 'Artist' in self.track else '') + '","title":"' + (self.track['Title'] if 'Title' in self.track else '') + '","genre":"' + (self.track['Genre'] if 'Genre' in self.track else '') + '","duration":' + str((self.track['Duration'] if 'Duration' in self.track else '')) + '}', retain=True)

    def announceStatus(self):
        client.publish(self.mqttTopicPrefix + 'status', self.status, retain=True)

    def announceConnected(self):
        client.publish(self.mqttTopicPrefix + 'connected', self.connected, retain=True)

    def announceState(self):
        client.publish(self.mqttTopicPrefix + 'state', self.state, retain=True)

    def announceDiscoverable(self):
        client.publish(self.mqttTopicPrefix + 'discoverable', self.discoverable, retain=True)

    def announceDevice(self):
        client.publish(self.mqttTopicPrefix + 'device', '{"alias":"' + self.deviceAlias + '"}', retain=True)

    def next(self):
        self.player.Next(dbus_interface=PLAYER_IFACE)

    def previous(self):
        self.player.Previous(dbus_interface=PLAYER_IFACE)

    def play(self):
        self.player.Play(dbus_interface=PLAYER_IFACE)

    def pause(self):
        self.player.Pause(dbus_interface=PLAYER_IFACE)

    def volumeUp(self):
        self.control.VolumeUp(dbus_interface=CONTROL_IFACE)
        self.transport.VolumeUp(dbus_interface=TRANSPORT_IFACE)

    def volumeDown(self):
        self.control.VolumeDown(dbus_interface=CONTROL_IFACE)
        self.transport.VolumeDown(dbus_interface=TRANSPORT_IFACE)

    def onMessage(self, client, userdata, message):
        if (message.payload == 'play'):
            self.play()
        elif (message.payload == 'pause'):
            self.pause()
        elif (message.payload == 'next'):
            self.next()
        elif (message.payload == 'previous'):
            self.previous()


    def shutdown(self):
        client.loop_stop()
        if self.mainloop:
            self.mainloop.quit()


    """Pairing agent methods"""
    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        print("RequestPinCode (%s)" % (device))
        self.trustDevice(device)
        return "0000"

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        """Always confirm"""
        self.trustDevice(device)
        return

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        """Always authorize"""
        return

    def trustDevice(self, path):
        """Set the device to trusted"""
        device_properties = dbus.Interface(self.bus.get_object(SERVICE_NAME, path), "org.freedesktop.DBus.Properties")
        device_properties.Set(DEVICE_IFACE, "Trusted", True)

    def untrustDevice(self, path):
        """Set the device to trusted"""
        device_properties = dbus.Interface(self.bus.get_object(SERVICE_NAME, path), "org.freedesktop.DBus.Properties")
        device_properties.Set(DEVICE_IFACE, "Trusted", False)

    def registerAgent(self):
        """Register BluePlayer as the default agent"""
        manager = dbus.Interface(self.bus.get_object(SERVICE_NAME, "/org/bluez"), "org.bluez.AgentManager1")
        manager.RegisterAgent(BluePlayer.AGENT_PATH, BluePlayer.CAPABILITY)
        manager.RequestDefaultAgent(BluePlayer.AGENT_PATH)

    def startPairing(self):
        """Make the adpater discoverable"""
        adapter_path = findAdapter().object_path
        adapter = dbus.Interface(self.bus.get_object(SERVICE_NAME, adapter_path), "org.freedesktop.DBus.Properties")
        adapter.Set(ADAPTER_IFACE, "Discoverable", True)


time.sleep(2)

player = None
client = None

try:
    client = mqtt.Client()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.connect(MQTT_HOST, MQTT_PORT)

    player = BluePlayer()
    player.start()


except KeyboardInterrupt as ex:
    print("BluePlayer cancelled by user")

except Exception as ex:
    print("How embarrassing. The following error occurred {}".format(ex))
    traceback.print_exc()

finally:
    if client:
        client.disconnect()
    player.shutdown()

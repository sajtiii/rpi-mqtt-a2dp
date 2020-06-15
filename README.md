# Raspberry PI Bluetooth music player with MQTT control

Turn your Raspberry PI into a Bluetooth audio receiver, and control it via MQTT.

#### Pull requestst are welcomed.

### Installation
Install a copy of the Raspberry OS image on your PI.
Open raspi-config, using:
```sh
sudo raspi-config
```
And force the audio output to be the 3.5mm jack. `Advanced > Audio > 3.5mm jack`

Download a copy of this software, and open the following files: `files/a2dp-agent.py` and `files/btvol-control.py`.
*(You can download the code and edit on your local machine, or you can download it directly to your PI, and edit it using your favourite editor. [I'm in the Nano gang])*

Search for the part, where it says the following, and specify your MQTT broker's details.
```python
MQTT_HOST = 'localhost'
MQTT_PORT = 1883
MQTT_USERNAME = ''
MQTT_PASSWORD = ''
```
Now you can install the scripts using:
```sh
$ cd /path/where/install/file/is/located
$ sudo bash install.sh
```
Durring installation you can assing a new hostname to your PI, and also, you can choose a pretty name, that will be displayed to bluetooth clients.

After installation, you need to restart your PI.

*Please note that, in some cases, if the services wont working, you need to open raspi-config again, and set the 3.5mm jack as the output, and restart again.*

For production environments...

```sh
$ npm install --production
$ NODE_ENV=production node app
```


### MQTT Topics
- `{prefix}/volume`: Getting the current volume (0-100)
- `{prefix}/volume/set`: Setting a new volume (0-100)
- `{prefix}/track`: Getting track info. (JSON object containing: artist, title, album, duration, genre)
- `{prefix}/track/action`: Moving to the next or previous track (Valid payload values: next, previous)
- `{prefix}/status`: Getting the status of the playback (play, pause, stop)
- `{prefix}/status/set`: Starting or stopping playback (Valid payload values: play, pause)

### Credits
This code is created using the following previously available packages:
- **Blueplayer** by: Douglas6 (https://github.com/Douglas6/blueplayer/)
Bluetooth connection and track management
- **rpi-audio-receiver** by: nicokaiser (https://github.com/nicokaiser/rpi-audio-receiver)
Installation scripts and .service files


##### Buy me a Coffee
If you find this project useful, please consider supporting my work on [Patreon](https://www.patreon.com/sajtii) or [PayPal](paypal.me/cheee)

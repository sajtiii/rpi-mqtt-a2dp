#!/bin/bash -e

if [[ $(id -u) -ne 0 ]] ; then echo "Please run as root" ; exit 1 ; fi

# Disable WiFi for better Bluetooth experience
echo "dtoverlay=disable-wifi" >> /boot/config.txt

read -p "Hostname [$(hostname)]: " HOSTNAME
raspi-config nonint do_hostname ${HOSTNAME:-$(hostname)}

CURRENT_PRETTY_HOSTNAME=$(hostnamectl status --pretty)
read -p "Pretty hostname [${CURRENT_PRETTY_HOSTNAME:-Raspberry Pi}]: " PRETTY_HOSTNAME
hostnamectl set-hostname --pretty "${PRETTY_HOSTNAME:-${CURRENT_PRETTY_HOSTNAME:-Raspberry Pi}}"

echo "Adding Mosquitto server repository"
wget http://repo.mosquitto.org/debian/mosquitto-repo.gpg.key
apt-key add mosquitto-repo.gpg.key
wget http://repo.mosquitto.org/debian/mosquitto-buster.list -P /etc/apt/sources.list.d/

echo "Updating packages"
apt update
apt upgrade -y


echo "Installing services"
apt install -y --no-install-recommends alsa-base alsa-utils bluealsa python-gobject python-smbus python-dbus python-paho-mqtt python-alsaaudio mosquitto


# WoodenBeaver sounds
mkdir -p /usr/local/share/sounds/WoodenBeaver/stereo
if [ ! -f /usr/local/share/sounds/WoodenBeaver/stereo/device-added.wav ]; then
    cp files/device-added.wav /usr/local/share/sounds/WoodenBeaver/stereo/
fi
if [ ! -f /usr/local/share/sounds/WoodenBeaver/stereo/device-removed.wav ]; then
    cp files/device-removed.wav /usr/local/share/sounds/WoodenBeaver/stereo/
fi

# Bluetooth settings
cat <<'EOF' > /etc/bluetooth/main.conf
[General]
Class = 0x200414
DiscoverableTimeout = 0
[Policy]
AutoEnable=true
EOF

# Make Bluetooth discoverable after initialisation
mkdir -p /etc/systemd/system/bthelper@.service.d
cat <<'EOF' > /etc/systemd/system/bthelper@.service.d/override.conf
[Service]
ExecStartPost=/usr/bin/bluetoothctl discoverable on
ExecStartPost=/bin/hciconfig %I piscan
ExecStartPost=/bin/hciconfig %I sspmode 1
EOF

# Copy agent file
cp files/a2dp-agent.py /usr/local/bin/a2dp-agent.py
chmod 755 /usr/local/bin/a2dp-agent.py

cat <<'EOF' > /etc/systemd/system/a2dp-agent.service
[Unit]
Description=Bluetooth A2DP Agent
Requires=bluetooth.service
After=bluetooth.service
[Service]
ExecStart=/usr/local/bin/a2dp-agent.py
RestartSec=5
Restart=always
[Install]
WantedBy=multi-user.target
EOF
systemctl enable a2dp-agent.service

# Copy btvol-control file
cp files/btvol-control.py /usr/local/bin/btvol-control.py
chmod 755 /usr/local/bin/btvol-control.py

cat <<'EOF' > /etc/systemd/system/btvol-control.service
[Unit]
Description=Bluetooth and Volume management
[Service]
ExecStart=/usr/local/bin/btvol-control.py
RestartSec=5
Restart=always
[Install]
WantedBy=multi-user.target
EOF
systemctl enable btvol-control.service

# ALSA settings
sed -i.orig 's/^options snd-usb-audio index=-2$/#options snd-usb-audio index=-2/' /lib/modprobe.d/aliases.conf

# BlueALSA
mkdir -p /etc/systemd/system/bluealsa.service.d
cat <<'EOF' > /etc/systemd/system/bluealsa.service.d/override.conf
[Service]
ExecStart=
ExecStart=/usr/bin/bluealsa -i hci0 -p a2dp-sink
RestartSec=5
Restart=always
EOF

cat <<'EOF' > /etc/systemd/system/bluealsa-aplay.service
[Unit]
Description=BlueALSA aplay
Requires=bluealsa.service
After=bluealsa.service sound.target
[Service]
Type=simple
User=root
ExecStartPre=/bin/sleep 2
ExecStart=/usr/bin/bluealsa-aplay --pcm-buffer-time=250000 00:00:00:00:00:00
RestartSec=5
Restart=always
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable bluealsa-aplay

# Bluetooth udev script
cat <<'EOF' > /usr/local/bin/bluetooth-udev
#!/bin/bash
if [[ ! $NAME =~ ^\"([0-9A-F]{2}[:-]){5}([0-9A-F]{2})\"$ ]]; then exit 0; fi
action=$(expr "$ACTION" : "\([a-zA-Z]\+\).*")
if [ "$action" = "add" ]; then
    bluetoothctl discoverable off
    if [ -f /usr/local/share/sounds/WoodenBeaver/stereo/device-added.wav ]; then
        aplay -q /usr/local/share/sounds/WoodenBeaver/stereo/device-added.wav
    fi
fi
if [ "$action" = "remove" ]; then
    if [ -f /usr/local/share/sounds/WoodenBeaver/stereo/device-removed.wav ]; then
        aplay -q /usr/local/share/sounds/WoodenBeaver/stereo/device-removed.wav
    fi
    bluetoothctl discoverable on
fi
EOF
chmod 755 /usr/local/bin/bluetooth-udev

cat <<'EOF' > /etc/udev/rules.d/99-bluetooth-udev.rules
SUBSYSTEM=="input", GROUP="input", MODE="0660"
KERNEL=="input[0-9]*", RUN+="/usr/local/bin/bluetooth-udev"
EOF

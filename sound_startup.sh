#!/bin/bash

sudo alsactl --file /home/user/.config/asound.state restore 
aplay -D plughw:CARD=seeed2micvoicec,DEV=0 /home/user/JarvisChatBot/sounds/winxp_startup.wav
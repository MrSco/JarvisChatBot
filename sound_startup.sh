#!/bin/bash

alsactl --file /home/rocco/.config/asound.state restore 
aplay -D plughw:CARD=seeed2micvoicec,DEV=0 /home/rocco/JarvisChatBot/sounds/winxp_startup.wav
#!/bin/bash

sudo alsactl --file ~/.config/asound.state restore 
aplay -D plughw:CARD=seeed2micvoicec,DEV=0 ~/JarvisChatBot/sounds/winxp_startup.wav
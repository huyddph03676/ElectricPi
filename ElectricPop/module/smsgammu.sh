#!/bin/bash

net_sms=$(dmesg | awk '/GSM.*ttyUSB[0-9]/ {print $NF}' | tail -1)

if [[ $net_sms != '' ]] ; then 
    echo "Found path of GSM Modem ! Starting send SMS!"
    sed -i "s|tty.*|$net_sms|" ~/.gammurc
    echo $1 | gammu --sendsms TEXT $2
else
    echo "Cannot send SMS! Please try again !"
fi
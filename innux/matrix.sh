#!/bin/bash
chars=(7 M O C T X 0 1 █ ▓ ▒ ░)
clear
while :; do
    tput cup $((RANDOM % $(tput lines))) $((RANDOM % $(tput cols)))
    [ $((RANDOM % 10)) -eq 0 ] && echo -ne "\033[1;31m" || echo -ne "\033[1;32m"
    echo -ne "${chars[$((RANDOM % ${#chars[@]}))]}\033[0m"
    sleep 0.01
done

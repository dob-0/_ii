#!/bin/bash
set -e
cp ~/_ii/ii-visuals.service /etc/systemd/system/
cp ~/_ii/ii-web.service /etc/systemd/system/
cp ~/_ii/ii-ctrl.service /etc/systemd/system/

systemctl daemon-reload

# stop getty on tty1 (visuals takes it over)
systemctl disable getty@tty1.service
systemctl stop getty@tty1.service

# enable and start all three
systemctl enable ii-visuals.service ii-web.service ii-ctrl.service
systemctl start ii-visuals.service ii-web.service ii-ctrl.service

echo ''
echo '=== STATUS ==='
systemctl status ii-visuals.service --no-pager -l
systemctl status ii-web.service --no-pager -l
systemctl status ii-ctrl.service --no-pager -l

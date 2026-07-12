#!/usr/bin/env bash
set -euo pipefail

UUID=kasual-helper@consoledesktop.org
TARGET=~/.local/share/gnome-shell/extensions/"$UUID"

rm -f /run/user/1000/gnome-shell-disable-extensions

mkdir -p "$TARGET"
cp `dirname $0`/../packaging/gnome-extension/"$UUID"/* "$TARGET"/

gsettings set org.gnome.shell disable-user-extensions false
gnome-extensions enable "$UUID"
gnome-extensions info "$UUID"

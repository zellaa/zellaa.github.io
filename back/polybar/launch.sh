#!/bin/bash
 
# Terminate already running bar instances
killall -q polybar
 
# Wait until the processes have been shut down
while pgrep -u $UID -x polybar >/dev/null; do sleep 1; done

outputs=$(xrandr --query | grep " connected" | cut -d" " -f1)
tray_output=eDP1
for m in $outputs; do
    MONITOR=$m polybar --reload julian &
done


# Launch Polybar, using default config location ~/.config/polybar/config
#polybar -r julian &

#polybar -r zella &
#polybar -r middle &
echo "Polybar launched..."
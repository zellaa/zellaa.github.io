#!/bin/sh
(setxkbmap -query | grep -q "layout:\s\+gb") && setxkbmap us || setxkbmap gb

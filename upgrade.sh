#!/bin/bash

# to run copy cookie from your browser with enough privileges
set -e

for (( ; ; ))
do
#   curl --fail --cookie "" 'https://smartbudgetapp2.appspot.com/sbs_upgrade.php?batch=100'
   curl --fail --cookie "" 'https://smartbudgetapp2.appspot.com/sbs_destroy.php?batch=100'
   echo ""
   sleep 0.5
done

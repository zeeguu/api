#!/bin/bash

echo -n DB Password: 
read -s password
echo $password

db=zeeguu

query="select e.source_id, substring(o.outcome, 1, 40), e.solving_speed from $db.exercise as e, $db.exercise_outcome as o where e.outcome_id = o.id order by (e.id) desc LIMIT 20"


unhide_cursor() {
    printf '\e[?25h'
}
trap unhide_cursor EXIT

# Hide the cursor (there is probably a much better way to do this)
printf '\e[?25l'
clear 
while true ; do
    # Move the cursor to the top of the screen but don't clear the screen
    printf '\033[;H' 
    mysql -u $db -p$password -e "$query"
    sleep 1
done


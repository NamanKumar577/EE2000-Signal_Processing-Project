#!/bin/bash
# usage: sweep.sh "cfg1" "cfg2" ...   -> prints mean F1 per set for each config
cd /d/signal_project/tools/accuracy
for c in "$@"; do
  ../../venv/Scripts/python.exe v5c.py $c >/dev/null 2>&1
  tag=$(echo "$c" | tr ' ' '_'); [ -z "$tag" ] && tag=default
  ../../venv/Scripts/python.exe -c "
import pandas as pd; d=pd.read_csv('results_v5c_$tag.csv'); g=d.groupby('set').f1.mean().round(2).to_dict(); print('$c'.ljust(40), g)"
done

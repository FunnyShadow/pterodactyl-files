#!/bin/bash

while IFS= read -r eggs; do
  tag="egg-${eggs}"
  input="./eggs/json/tools/${tag}.yml"
  output="./eggs/yml/tools/${tag}.json"
  python3 tool.py y2j -i "${input}" -o "${output}"
done < egglist
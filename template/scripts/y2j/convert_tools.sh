#!/bin/bash

while IFS= read -r eggs; do
  tag="egg-${eggs}"
  input="./eggs/json/tools/${tag}.json"
  output="./eggs/yml/tools/${tag}.yml"
  python3 tool.py y2j -i "${input}" -o "${output}"
done < egglist
#!/bin/bash

while IFS= read -r eggs; do
  tag="egg-${eggs}"
<<<<<<< HEAD
  input="./eggs/json/tools/${tag}.json"
  output="./eggs/yml/tools/${tag}.yml"
=======
  input="./eggs/json/tools/${tag}.yml"
  output="./eggs/yml/tools/${tag}.json"
>>>>>>> 1cb7adf1ae224aec2d6de6b63e7e59e9e629fc23
  python3 tool.py y2j -i "${input}" -o "${output}"
done < egglist
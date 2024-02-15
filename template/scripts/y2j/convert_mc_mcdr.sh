#!/bin/bash

while IFS= read -r eggs; do
  tag="egg-${eggs}"
<<<<<<< HEAD
  input="./eggs/json/minecraft/mcdr/${tag}.yml"
  output="./eggs/yml/minecraft/mcdr/${tag}.json"
=======
  input="./eggs/json/minecraft/mcdr/${tag}.json"
  output="./eggs/yml/minecraft/mcdr/${tag}.yml"
>>>>>>> 1cb7adf1ae224aec2d6de6b63e7e59e9e629fc23
  python3 tool.py y2j -i "${input}" -o "${output}"
done < egglist
#!/bin/bash

## Variables
# Features
DEBUG=false

# Script used
directory="eggs"
mode="y2j"
file_count=0

## Functions
print_log() {
  case "$1" in
  "DEBUG")
    printf "\033[90m[ \033[96mDEBUG\033[0m \033[90m] \033[96m%s\033[0m\n" "$2"
    return
    ;;
  "INFO")
    printf "\033[90m[ \033[92mINFO\033[0m \033[90m] \033[92m%s\033[0m\n" "$2"
    return
    ;;
  "WARN")
    printf "\033[90m[ \033[93mWARN\033[0m \033[90m] \033[93m%s\033[0m\n" "$2"
    return
    ;;
  "ERROR")
    printf "\033[90m[ \033[91mERROR\033[0m \033[90m] \033[91m%s\033[0m\n" "$2"
    return
    ;;
  "FATAL")
    printf "\033[90m[ \033[41m\033[37mFATAL\033[0m \033[90m] \033[41m\033[37m%s\033[0m\n" "$2"
    exit 1
    ;;
  esac
}

arg_parser() {
  while getopts "d:m:o:hv" opt; do
    case ${opt} in
    d)
      directory=$OPTARG
      ;;
    m)
      if [ "$OPTARG" = "y2j" ] || [ "$OPTARG" = "j2y" ]; then
        mode=$OPTARG
      else
        print_log "FATAL" "Invalid mode. Please choose either 'y2j' or 'j2y'."
      fi
      ;;
    o)
      eval "$OPTARG"
      ;;
    h)
      echo "Usage: convert_tools.sh [OPTIONS]"
      echo ""
      echo "  -d <directory>  Directory to search for files"
      echo "  -m <mode>       Mode to use (y2j or j2y)"
      echo "  -o <env>        Override environment variables"
      echo "  -h              Show this help message"
      echo "  -v              Show version"
      exit 0
      ;;
    v)
      echo "v1.0 | Tue Mar 12 04:44:06 PM CST 2024"
      exit 0
      ;;
    \?)
      print_log "FATAL" "Invalid option: $OPTARG" 1>&2
      ;;
    :)
      print_log "FATAL" "Invalid option: $OPTARG requires an argument" 1>&2
      ;;
    esac
  done
  shift $((OPTIND - 1))
}

main() {
  case $mode in
  "y2j")
    local input_exts=("yaml" "yml")
    local output_ext="json"
    print_log "INFO" "Converting YAML to JSON"
    ;;
  "j2y")
    local input_exts=("json")
    local output_ext="yaml"
    print_log "INFO" "Converting JSON to YAML"
    ;;
  esac

  for input_ext in "${input_exts[@]}"; do
    while IFS= read -r file; do
      local input="$file"
      local output="${input%."$input_ext"}.$output_ext"

      if $DEBUG; then
        print_log "DEBUG" "Converting file $input -> $output"
      fi

      if ! python3 convert.py -i "${input}" -o "${output}" 2>convert_tool_temp_err_buffer; then
        print_log "ERROR" "Error converting file: $input"
        cat convert_tool_temp_err_buffer
      else
        ((file_count++))
      fi
    done < <(find "$directory" -name "*.$input_ext")
  done

  if [ $file_count -eq 0 ]; then
    print_log "WARN" "No matching files were detected!"
  fi

  rm -rf convert_tool_temp_err_buffer
}

## Start
arg_parser "$@"
print_log "INFO" "Start converting files"
main
print_log "INFO" "Done, Total $file_count files converted"

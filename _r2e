#compdef r2e

# Start of options' arguments' helpers

local common_option_help=('(- :)'{-h,--help}'[show this help message and exit]')
(( $+functions[__r2e_command] )) ||
__r2e_command(){
  local -a commands=(
    'new:Create a new feed database'
    'email:Update the default target email address'
    'add:Add a new feed to the database'
    'run:Fetch feeds and send entry emails'
    'list:List all the feeds in the database'
    'pause:Pause a feed (disable fetching)'
    'unpause:Unpause a feed (enable fetching)'
    'delete:Remove a feed from the database'
    'reset:Forget dynamic feed data (e.g. to re-send old entries)'
    'opmlimport:Import configuration from OPML'
    'opmlexport:Export configuration to OPML'
  )
  _describe -t commands 'command' commands "$@"
}
(( $+functions[___r2e_feeds_cache_policy] )) ||
___r2e_feeds_cache_policy(){
  local config="${XDG_CONFIG_HOME:-${HOME}/.config}/rss2email.cfg"
  local cache_file="$1"
  local cache_status=1
  if [[ ( -f ${cache_file} && -f ${config} ) ]]; then
    if [[ "$config" -nt "${cache_file}" ]]; then
      cache_status=0
    fi
  fi
  return cache_status
}
(( $+functions[__r2e_feeds] )) ||
__r2e_feeds(){
  local config="$1"
  local feeds_raw feeds i
  if [[ ! -z ${config} ]];then
    feeds_raw=(${(f)"$(_call_program r2e_feeds r2e --config "$config" list)"})
    for i in "${feeds_raw[@]}"; do
      feeds+=(${${i#[0-9]*: \[\*\] }% \(*})
    done
  else
    config="${XDG_CONFIG_HOME:-${HOME}/.config}/rss2email.cfg"
    local update_policy
    zstyle -s ":completion:${curcontext}:" cache-policy update_policy
    if [[ -z "$update_policy" ]]; then
      zstyle ":completion:${curcontext}:" cache-policy ___r2e_feeds_cache_policy
    fi
    if _cache_invalid r2e_feeds; then
      feeds_raw=(${(f)"$(_call_program r2e_feeds r2e list)"})
      for i in "${feeds_raw[@]}"; do
        feeds+=(${${i#[0-9]*: \[\*\] }% \(*})
      done
      _store_cache r2e_feeds feeds
    else
      _retrieve_cache r2e_feeds
    fi
  fi
  if [[ ! -z ${feeds} ]]; then
    _values feeds ${feeds}
  else
    _message -r "rss2email doesn't have any feeds"
  fi
}

# End of options' arguments' helpers & Start of sub commands helpers

(( $+functions[_r2e_opmlexport] )) ||
_r2e_opmlexport(){
  _arguments \
    "${common_option_help[@]}" \
    '1: :_files -g "*.opml"'
}
(( $+functions[_r2e_opmlimport] )) ||
_r2e_opmlimport(){
  _arguments \
    "${common_option_help[@]}" \
    '1: :_files -g "*.opml"'
}
(( $+functions[_r2e_reset] )) ||
_r2e_reset(){
  _arguments \
    "${common_option_help[@]}" \
    "*: :{__r2e_feeds ${opt_args[--config]} ${opt_args[-c]}}"
}
(( $+functions[_r2e_delete] )) ||
_r2e_delete(){
  _arguments \
    "${common_option_help[@]}" \
    "*: :{__r2e_feeds ${opt_args[--config]} ${opt_args[-c]}}"
}
(( $+functions[_r2e_unpause] )) ||
_r2e_unpause(){
  _arguments \
    "${common_option_help[@]}" \
    "*: :{__r2e_feeds ${opt_args[--config]} ${opt_args[-c]}}"
}
(( $+functions[_r2e_pause] )) ||
_r2e_pause(){
  _arguments \
    "${common_option_help[@]}" \
    "*: :{__r2e_feeds ${opt_args[--config]} ${opt_args[-c]}}"
}
(( $+functions[_r2e_list] )) ||
_r2e_list(){
  _arguments \
    "${common_option_help[@]}"
}
(( $+functions[_r2e_run] )) ||
_r2e_run(){
  _arguments \
    "${common_option_help[@]}" \
    {-n,--no-send}"[fetch feeds, but don't send email]" \
    "*: :{__r2e_feeds ${opt_args[--config]} ${opt_args[-c]}}"
}
(( $+functions[_r2e_add] )) ||
_r2e_add(){
  _arguments \
    "${common_option_help[@]}" \
    '1:name of the new feed:' \
    '2:location of the new feed:_urls' \
    '3:target email for the new feed:_email_addresses'
}
(( $+functions[_r2e_email] )) ||
_r2e_email(){
  _arguments \
    "${common_option_help[@]}" \
    '1:default target email for the email feed database:_email_addresses'
}
(( $+functions[_r2e_new] )) ||
_r2e_new(){
  _arguments \
    "${common_option_help[@]}" \
    '1:default target email for the email feed database:_email_addresses'
}

# The real thing
_arguments -C \
  "${common_option_help[@]}" \
  '(- :)'{-v,--version}"[show program's version number and exit]" \
  '(- :)--full-version[print the version information of all related packages and exit]' \
  {-c,--config}'[path to the configuration file]: :_files' \
  {-d,--data}'[path to the feed data file]: :_files' \
  {-V,--verbose}'[increment verbosity]' \
  '1: :__r2e_command' \
  '*::arg:->args'

case "$state" in
  (args)
    curcontext="${curcontext%:*:*}:r2e-${words[1]}:"
    if [[ $? != 1 ]]; then
      _call_function ret _r2e_${words[1]}
    fi
esac

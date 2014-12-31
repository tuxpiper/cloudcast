#!/bin/bash

set -e

: ${ANSIBLE_HOME:?} ${ANSIBLE_VERSION:?}

{ if [ -z "$(which virtualenv)" ]; then pip install virtualenv==12.0.4 ; else true ; fi } && \
  { if [ ! -f $ANSIBLE_HOME/bin/activate ]; then virtualenv --system-site-packages $ANSIBLE_HOME ; else true ; fi }

. $ANSIBLE_HOME/bin/activate

ver_check() {
    local IFS=.
    local mod="$1" w=($2)
    local v=($(python -c 'import '${mod}'; print '${mod}'.__version__;' 2> /dev/null))
    [ "$?" -ne 0 ] && return 1;
    [[ ( ! -z "${v[0]}" ) && ( ${v[0]} -ge ${w[0]} ) ]] && \
      [[ ( ! -z "${v[1]}" ) && ( ${v[1]} -ge ${w[1]} ) ]] && \
      [[ ( ! -z "${v[2]}" ) && ( ${v[2]} -ge ${w[2]} ) ]]
}

ver_check ansible $ANSIBLE_VERSION && exit 0

eval `lsb_release -irs | awk 'NR == 1 { printf "export LSB_DISTRO=%s\n", $1 } NR == 2 { printf "export LSB_VERSION=%s\n", $1 }'`

case "$LSB_DISTRO" in
  Ubuntu)
    if [ "$LSB_VERSION" == "14.04" ]; then
      ver_check Crypto 2.6.1 || { apt-get update && apt-get install -y python-crypto ; }
    else
      echo "ERROR: Unhandled Ubuntu version '$LSB_VERSION'"
      exit 1
    fi
    ;;
  *)
    echo "ERROR: Unhandled distro '$LSB_DISTRO'"
    exit 1
    ;;
esac

pip install ansible==${ANSIBLE_VERSION}


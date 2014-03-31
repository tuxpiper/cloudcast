
FATAL() { code=$1; shift; echo "[FATAL] $*" >&2; exit $code; }
ERROR() { echo "[ERROR] $*" >&2 ; }
WARN()  { echo "[WARNING] $*" >&2 ; }
INFO()  { echo "[INFO] $*" >&2 ; }

{ : ${SHELL_ISCM_NAME:?} ; } || FATAL 1 "Missing required vars"

get_instance_id() { wget -q -O - http://169.254.169.254/latest/meta-data/instance-id ; }
export AWS__INSTANCE_ID=$(get_instance_id)

load_shell_vars() {
    local decode_vars_py=$(cat <<"EOF"
import json, sys
doc = json.load(sys.stdin, encoding="latin-1")
for (k,v) in doc.iteritems():
    if not isinstance(v,str) and not isinstance(v,unicode):
        continue
    if isinstance(k,unicode): k = k.encode('latin-1')
    if isinstance(v,unicode): v = v.encode('latin-1')
    print "%s=\"%s\"" % (k, v.replace('"', '\\"'))
EOF
)
    local stack_vars_file=$(mktemp)
    { cfn-get-metadata -s $AWS__STACK_NAME -r $AWS__STACKEL_NAME \
        --access-key $AWS__BOOTSTRAP_KEY_ID \
        --secret-key $AWS__BOOTSTRAP_SECRET_KEY \
        --region $AWS__REGION -k ${SHELL_ISCM_METADATA_VARS_KEY} | \
        python -c "$decode_vars_py" > $stack_vars_file ; } || \
        FATAL 1 "Unable to load stack variables"
    source $stack_vars_file
    rm $stack_vars_file
}

[ -n "${SHELL_ISCM_METADATA_VARS_KEY}" ] && load_shell_vars

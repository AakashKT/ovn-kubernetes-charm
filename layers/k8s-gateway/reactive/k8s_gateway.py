import os
import json
import re
import sys
import subprocess
import time
import urllib.request as urllib2

from charmhelpers.core.host import (
    service_start,
    service_stop,
    log,
    mkdir,
    write_file,
)

from charmhelpers.fetch import (
    apt_install,
    apt_update,
    apt_upgrade
)

from charms.reactive import (
    when,
    when_not,
    hook,
    set_state
)


#########################################################################
# Common functions
#########################################################################

def run_command(command=None):

    if command is None:
        return False;

    log('Running Command "%s"' % command);
    try:
        return subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT).decode('utf-8').replace('\n', '');
    except subprocess.CalledProcessError as e:
        log('Error running "%s" : %s' % (command, e.output));

        return False;

def get_my_ip():
    return json.loads(urllib2.urlopen('https://api.ipify.org/?format=json').read().decode('utf-8'))['ip'];


#########################################################################
# Hooks and reactive handlers
#########################################################################

@when_not('k8s-gateway.installed')
def install_k8s_gateway():

    run_command('git clone https://github.com/openvswitch/ovn-kubernetes /tmp/ovn-kubernetes');
    os.chdir('/tmp/ovn-kubernetes');
    run_command('sudo pip2 install .');

    op = run_command('ovn-k8s-util nics-to-bridge ens4');
    log('Bridge create output :');
    log(op);

    op = run_command('dhclient -r brens4');
    log('Release interface : %s' % (op));
    op = run_command('dhclient brens4');
    log('Fresh assign : %s' % (op));

    local_ip = get_my_ip();
    gateway_ip = run_command('ip route | grep default').split(' ')[2];
    hostname = run_command('hostname');

    op = run_command('ovn-k8s-overlay gateway-init \
                    --cluster-ip-subnet="192.168.0.0/16" \
                    --bridge-interface brens4 \
                    --physical-ip %s/24 \
                    --node-name="%s-gateway" \
                    --default-gw %s' % (local_ip, hostname, gateway_ip));
    log('Gateway init output :');
    log(op);

    op = run_command('ovn-k8s-gateway-helper --physical-bridge=brens4 \
                        --physical-interface=ens4 --pidfile --detach');
    log('Daemon start : %s' % (op));

    set_state('k8s-gateway.installed')

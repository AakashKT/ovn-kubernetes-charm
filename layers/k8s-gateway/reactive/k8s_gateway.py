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

@when('k8s-master-config.available')
@when_not('k8s-gateway.installed')
def install_k8s_gateway(k8s_master):
    k8s_api_ip = k8s_master.get_config('k8s_api_ip');
    run_command('ovs-vsctl set Open_vSwitch . \
                    external_ids:k8s-api-server="%s:8080"' % (k8s_api_ip));

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

    op = run_command('ovn-k8s-overlay gateway-init \
                    --cluster-ip-subnet="192.168.0.0/16" \
                    --bridge-interface brens4 \
                    --physical-ip %s/24 \
                    --node-name="kube-minion2" \
                    --default-gw %s' % (local_ip, gateway_ip));
    log('Gateway init output :');
    log(op);

    op = run_command('ovn-k8s-gateway-helper --physical-bridge=brens4 \
                        --physical-interface=ens4 --pidfile --detach');
    log('Daemon start : %s' % (op));

    set_state('k8s-gateway.installed')


@when('ovn-central-config.available')
@when_not('onetime-setup.done')
def onetime_setup(ovn_central):
    central_ip = ovn_central.get_config('central_ip');
    local_ip = get_my_ip();

    run_command('ovs-vsctl set Open_vSwitch . external_ids:ovn-remote="tcp:%s:6642" \
                        external_ids:ovn-nb="tcp:%s:6641" \
                        external_ids:ovn-encap-ip=%s \
                        external_ids:ovn-encap-type="%s"' % (central_ip, central_ip, local_ip, 'stt'));

    run_command('ovs-vsctl set Open_vSwitch . external_ids:system-id=$(uuidgen)');
    run_command('/usr/share/openvswitch/scripts/ovn-ctl start_controller');

    set_state('onetime-setup.done');

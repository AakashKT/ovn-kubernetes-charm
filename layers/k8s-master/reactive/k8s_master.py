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

@when_not('k8s-master.installed')
@when('onetime-setup.done')
def install_k8s_master():

    run_command('ovs-vsctl set Open_vSwitch . external_ids:k8s-api-server="127.0.0.1:8080"');

    run_command('git clone https://github.com/openvswitch/ovn-kubernetes /tmp/ovn-kubernetes');

    os.chdir('/tmp/ovn-kubernetes');

    run_command('sudo pip2 install .');
    run_command('ovn-k8s-overlay master-init --cluster-ip-subnet="192.168.0.0/16" \
                    --master-switch-subnet="192.168.1.0/24" --node-name="kube-master" ')

    set_state('k8s-master.installed')


@when('ovn-central-comms.available')
@when_not('onetime-setup.done')
def onetime_setup(ovn):
    central_ip = ovn.get_central_ip();
    local_ip = get_my_ip();

    run_command('ovs-vsctl set Open_vSwitch . external_ids:ovn-remote="tcp:%s:6642" \
                        external_ids:ovn-nb="tcp:%s:6641" \
                        external_ids:ovn-encap-ip=%s \
                        external_ids:ovn-encap-type="%s"' % (central_ip, central_ip, local_ip, 'stt'));
    
    run_command('ovs-vsctl set Open_vSwitch . external_ids:system-id=$(uuidgen)');
    run_command('/usr/share/openvswitch/scripts/ovn-ctl start_controller');

    set_state('onetime-setup.done');

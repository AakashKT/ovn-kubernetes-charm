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

@when_not('ovn-central.installed')
def install_ovn_central():

    run_command('/usr/share/openvswitch/scripts/ovn-ctl start_northd');

    run_command('ovn-nbctl set-connection ptcp:6641');
    run_command('ovn-sbctl set-connection ptcp:6642');

    set_state('ovn-central.installed')


@when('ovn-central-comms.available', 'ovn-central.installed')
@when_not('onetime-setup.done')
def broadcast_and_setup(ovn):

    central_ip = get_my_ip();

    run_command('ovs-vsctl set Open_vSwitch . external_ids:ovn-remote="tcp:%s:6642" \
                        external_ids:ovn-nb="tcp:%s:6641" \
                        external_ids:ovn-encap-ip=%s \
                        external_ids:ovn-encap-type="%s"' % (central_ip, central_ip, central_ip, 'stt'));
    
    run_command('ovs-vsctl set Open_vSwitch . external_ids:system-id=$(uuidgen)');
    run_command('/usr/share/openvswitch/scripts/ovn-ctl start_controller');

    ovn.send_ip(central_ip);

    set_state('onetime-setup.done');


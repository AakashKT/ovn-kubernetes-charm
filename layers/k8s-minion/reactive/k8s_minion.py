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

@when('central-config.available')
@when_not('k8s-minion.installed')
def install_k8s_minion(ovn_central):
    local_ip = get_my_ip();
    central_ip = ovn_central.get_config('central_ip');
    hostname = run_command('hostname');

    """
    os.chdir('/etc/openvswitch');
    run_command('sudo ovs-pki req ovncontroller');
    run_command('sudo ovs-pki -b -d /vagrant/pki sign ovncontroller switch');
    """
    run_command('sudo ovs-vsctl set Open_vSwitch . \
                    external_ids:ovn-remote="tcp:%s:6642" \
                    external_ids:ovn-nb="tcp:%s:6641" \
                    external_ids:ovn-encap-ip=%s \
                    external_ids:ovn-encap-type=%s' % (central_ip, central_ip, local_ip, 'geneve'));
    """
    ovn_host_file = open('/etc/default/ovn-host', 'a');
    ovn_host_file.write('OVN_CTL_OPTS="--ovn-controller-ssl-key=/etc/openvswitch/ovncontroller-privkey.pem  \
                    --ovn-controller-ssl-cert=/etc/openvswitch/ovncontroller-cert.pem \
                    --ovn-controller-ssl-bootstrap-ca-cert=/etc/openvswitch/ovnsb-ca.cert"');
    ovn_host_file.close();
    """
    run_command('/usr/share/openvswitch/scripts/ovn-ctl restart_controller');

    run_command('ovs-vsctl set Open_vSwitch . \
                external_ids:k8s-api-server="%s:8080"' % (central_ip));

    run_command('git clone https://github.com/openvswitch/ovn-kubernetes /tmp/ovn-kubernetes');
    os.chdir('/tmp/ovn-kubernetes');
    run_command('sudo -H pip2 install .');
    run_command('ovn-k8s-overlay minion-init --cluster-ip-subnet="192.168.0.0/16" \
                    --minion-switch-subnet="192.168.2.0/24" --node-name="%s"' % (hostname));

    os.chdir('/tmp/');
    run_command('wget https://github.com/containernetworking/cni/releases/download/v0.5.2/cni-amd64-v0.5.2.tgz');
    run_command('sudo mkdir -p /opt/cni/bin');
    os.chdir('/opt/cni/bin/');
    run_command('sudo tar xvzf /tmp/cni-amd64-v0.5.2.tgz');

    set_state('k8s-minion.installed')

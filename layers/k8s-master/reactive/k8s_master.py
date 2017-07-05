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
def broadcast_config(ovn_central):
    central_ip = get_my_ip();

    config = {
        'central_ip' : central_ip,
    };
    ovn_central.send_config(config);

@when_not('ovn-central.installed')
def install_k8s_master():
    central_ip = get_my_ip();
    hostname = run_command('hostname');

    run_command('/usr/share/openvswitch/scripts/ovn-ctl start_northd');

    """
    os.chdir('/etc/openvswitch');
    run_command('sudo ovs-pki -d /vagrant/pki init --force');
    run_command('sudo ovs-pki req ovnsb && sudo ovs-pki self-sign ovnsb');
    run_command('sudo ovn-sbctl set-ssl /etc/openvswitch/ovnsb-privkey.pem \
                    /etc/openvswitch/ovnsb-cert.pem  /vagrant/pki/switchca/cacert.pem');
    run_command('sudo ovs-pki req ovnnb && sudo ovs-pki self-sign ovnnb');
    run_command('sudo ovn-nbctl set-ssl /etc/openvswitch/ovnnb-privkey.pem \
                    /etc/openvswitch/ovnnb-cert.pem  /vagrant/pki/switchca/cacert.pem');
    run_command('sudo ovs-pki req ovncontroller');
    run_command('sudo ovs-pki -b -d /vagrant/pki sign ovncontroller switch');
    ovn_host_file = open('/etc/default/ovn-host', 'a');
    ovn_host_file.write('OVN_CTL_OPTS="--ovn-controller-ssl-key=/etc/openvswitch/ovncontroller-privkey.pem  \
                    --ovn-controller-ssl-cert=/etc/openvswitch/ovncontroller-cert.pem \
                    --ovn-controller-ssl-bootstrap-ca-cert=/etc/openvswitch/ovnsb-ca.cert"');
    ovn_host_file.close();
    """

    run_command('ovn-nbctl set-connection ptcp:6641');
    run_command('ovn-sbctl set-connection ptcp:6642');

    run_command('ovs-vsctl set Open_vSwitch . external_ids:ovn-remote="tcp:%s:6642" \
                    external_ids:ovn-nb="tcp:%s:6641" \
                    external_ids:ovn-encap-ip=%s \
                    external_ids:ovn-encap-type="%s"' % (central_ip, central_ip, central_ip, 'geneve'));

    run_command('/usr/share/openvswitch/scripts/ovn-ctl restart_controller');
    run_command('sudo ovs-vsctl set Open_vSwitch . external_ids:k8s-api-server="0.0.0.0:8080"');

    run_command('git clone https://github.com/openvswitch/ovn-kubernetes /tmp/ovn-kubernetes');
    os.chdir('/tmp/ovn-kubernetes');
    run_command('sudo -H pip2 install .');
    run_command('sudo ovn-k8s-overlay master-init --cluster-ip-subnet="192.168.0.0/16" \
                    --master-switch-subnet="192.168.1.0/24" \
                    --node-name="%s"' % (hostname));

    run_command('sudo ovn-k8s-watcher --overlay --pidfile --log-file -vfile:info \
                    -vconsole:emer --detach');

    set_state('ovn-central.installed');
